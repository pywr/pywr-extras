import json
from pprint import pprint
import os

def get_node(data, name):
    for node in data["nodes"]:
        if node["name"] == name:
            return node
    raise KeyError("{} not found".format(name))

def add_node(data, **kwargs):
    for node_data in data['nodes']:
        if node_data['name'] == kwargs.get('name'):
            placeholder = node_data.get("placeholder", False)
            if placeholder:
                # node was just a placeholder, remove it
                remove_node(data, node_data["name"])
            else:
                update_node(data, **kwargs)
                return False

    data['nodes'].append(kwargs)
    return True

def add_connection(data, *args):
    for edge_data in data['edges']:
        if all(a == b for a, b in zip(edge_data, args)):
            raise ValueError('Edge from ({}) to ({}) already exists.'.format(*args[:2]))
    data['edges'].append(args)


def update_node(data, name, **kwargs):
    for node_data in data['nodes']:
        if node_data['name'] == name:
            node_data.update(kwargs)
            break
    else:
        raise ValueError('Node with name ({}) not found.'.format(name))

def update_parameter(data, name, **kwargs):
    param_data = data['parameters'][name]
    param_data.update(kwargs)

def join_models(filenames, data=None):
    if data is None:
        data = {
            "metadata": {
                "title": "Model template",
                "description": "",
                "minimum_version": "0.2dev0"
            },
            "solver": {"name": "glpk"},
            "timestepper": {
                "start": "1990-01-01",
                "end": "1999-12-31",
                "timestep": 7
            },
            "recorders": {}
        }
    if "nodes" not in data.keys():
        data["nodes"] = []
    if "edges" not in data.keys():
        data["edges"] = []
    if "parameters" not in data.keys():
        data["parameters"] = {}
    if "recorders" not in data.keys():
        data["recorders"] = {}

    for filename in filenames:
        with open(filename, "r") as f:
            include_data = json.loads(f.read())
        if "nodes" in include_data.keys():
            for node_data in include_data["nodes"]:
                if "placeholder" in node_data.keys():
                    continue
                add_node(data, **node_data)
#                 try:
#                     add_node(data, **node_data)
#                 except:
#                     print('Skipping second definition of node: {}'.format(node_data['name']))

        if "edges" in include_data.keys():
            for edge_data in include_data["edges"]:
                add_connection(data, *edge_data)


        if "parameters" in include_data.keys():
            data["parameters"].update(include_data["parameters"])

        if "recorders" in include_data.keys():
            data["recorders"].update(include_data["recorders"])

    return data

def add_baseline_demand_parameter(data, wrz_name, table, column):
    """
    Create an entry in the "parameters" section for a WRZ's baseline demand.
    """
    param = {
        "type": "constant",
        "table": table, #"url": url,
        "column": column,
        #"index_col": 2,  # Code column in the spreadsheet.
        "index": wrz_name
    }

    data["parameters"]["{}_BL_demand".format(wrz_name)] = param

def add_monthly_demand_profile(data, wrz_name, table):
    """
    Create an entry in the "parameters" section for a WRZ's monthly demand profile
    """

    param = {
        "type": "monthlyprofile",
        #"url": url,
        "table": table,
        "index": wrz_name,
        #"index_col": 0  # Code column in the spreadsheet
    }
    data["parameters"]["{}_demand_profile".format(wrz_name)] = param


def add_demand_saving_parameter(data, wrz_name, table, level_param_name, column_format="{wrz} - Level {level:d}"):
    """
    Create a compound demand saving

    """

    param = {
        "type": "indexedarray",
        "index_parameter": level_param_name,
        "params": [
            # Level 0 - no demand saving
            {
                "type": "constant",
                "values": 1.0
            },
            # Level 1
            {
                "type": "monthlyprofile",
                "table": table,
                "index": [1, wrz_name],
            },
            # Level 2
            {
                "type": "monthlyprofile",
                "table": table,
                "index": [2, wrz_name],
            },
            # Level 3
            {
                "type": "monthlyprofile",
                "table": table,
                "index": [3, wrz_name],
            },
            # Level 4
            {
                "type": "monthlyprofile",
                "table": table,
                "index": [4, wrz_name],
            },
        ]
    }

    data["parameters"]["{}_demand_saving".format(wrz_name)] = param


def add_demand_parameters(data, wrz_name, baseline_table, baseline_column, profile_table, saving_table, level_param_name):
    """
    Add the demand parameter for a WRZ

    The demand is the product of:
      - baseline demand
      - demand profile
      - demand saving factor (optional)

    If `level_param_name` is None no demand saving will be disabled.
    """

    add_baseline_demand_parameter(data, wrz_name, baseline_table, baseline_column)
    add_monthly_demand_profile(data, wrz_name, profile_table)

    params = [
        "{}_BL_demand".format(wrz_name),
        "{}_demand_profile".format(wrz_name),
    ]

    if level_param_name is not None:
        add_demand_saving_parameter(data, wrz_name, saving_table, level_param_name)

        params.append("{}_demand_saving".format(wrz_name))

    param = {
        "type": "aggregated",
        "agg_func": "product",
        "parameters": params
    }

    param_name = "{}_demand".format(wrz_name)
    data["parameters"][param_name] = param
    return param_name


def add_demand_saving_control_curve(data, reservoir, url, level):

    param = {
        "type": "monthlyprofile",
        "url": url,
        "index_col": [0, 1],
        "index": [level, reservoir]
    }

    data["parameter"]["{}_level_{:d}".format(reservoir, level)]


def add_demand_saving_index(data, reservoir, url, levels):

    for lvl in levels:
        add_demand_saving_control_curve(data, reservoir, url, level)

    param = {
        "type": "controlcurveindex",
        "storage_node": reservoir,
        "control_curves": ["{}_level_{:d}".format(reservoir, lvl) for lvl in levels]
    }
    data["parameter"]["{}_demand_saving_index".format(reservoir)]

    
def fix_external_urls(data):
    external_filenames = set()
    to_search = [data]
    while True:
        try:
            item = to_search.pop(0)
        except IndexError:
            break
        else:
            if isinstance(item, dict):
                for subitem in item.values():
                    if isinstance(subitem, dict):
                        to_search.append(subitem)
                try:
                    url = item["url"]
                except: pass
                else:
                    if os.path.isabs(url):
                        item["url"] = url = os.path.join("data", os.path.basename(url))
                    # HACK the directory character - Windows can deal with /, but Linux can't deal with \
                    item["url"] = item["url"].replace("\\", "/")
                    external_filenames.add(url)

    # pprint(external_filenames)