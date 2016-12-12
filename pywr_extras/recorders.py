from pywr.recorders import Recorder, ParameterRecorder
from ._recorders import ConstantParameterScaledRecorder, BinnedRecorder


class MetaRecorder(Recorder):
    def __init__(self, model, recorders=None, **kwargs):
        super(MetaRecorder, self).__init__(model, **kwargs)
        self.recorders = recorders

    def value(self):

        data = {}

        recorders = self.recorders
        if recorders is None:
            recorders = self.model.recorders

        for r in recorders:
            if isinstance(r, MetaRecorder):
                # Avoid recursion
                continue

            rdata = {
                'class': r.__class__.__name__,
            }

            try:
                rdata['value'] = r.aggregated_value()
            except NotImplementedError:
                pass

            try:
                rdata['node'] = r.node.name
            except AttributeError:
                pass

            try:
                rdata['all_values'] = list(r.values())
            except AttributeError:
                pass

            data[r.name] = rdata

        return data


class JsonMetaRecorder(MetaRecorder):
    def value(self):
        import json
        return json.dumps(super(JsonMetaRecorder, self).value(), sort_keys=True,
                          indent=4, separators=(',', ': '))

