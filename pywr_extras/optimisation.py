import numpy as np
from pywr.optimisation.moea import InspyredOptimisationModel
import inspyred
import copy
from ._optimisation import BinnedScenarioParameter, BinnedParameter
from .recorders import MetaRecorder

class BinnedScenarioCandidate:
    def __init__(self, initial_variables, members=None):
        self.variables = np.array(initial_variables)

        self.members = set()
        if members is not None:
            for m in members:
                self.members.add(m)

    @property
    def number_of_variables(self):
        return len(self.variables)

    @property
    def number_of_members(self):
        return len(self.members)

    def populate_variable_array(self, a):
        """Set the variables of a for the members of bin"""
        for m in self.members:
            a[m, :] = self.variables
        return a


class MultiBinCandidate:
    def __init__(self, number_of_bins, number_of_variables=None, bin_variables=None,
                 bin_members=None, all_valid_members=None):
        if number_of_variables is None and bin_variables is None:
            raise ValueError("Either number_of_variables or bin_variables must be given.")

        if number_of_variables is not None:
            bin_variables = np.random.random_integers((number_of_bins, number_of_variables))
        else:
            number_of_variables = len(bin_variables[0])

        if bin_members is None and all_valid_members is None:
            raise ValueError("Either bin_members or all_valid_members must be given.")

        if bin_members is not None:
            self.all_valid_members = [m for members in bin_members for m in members]
        else:
            self.all_valid_members = all_valid_members

        self.number_of_variables = number_of_variables
        self.bins = []
        for i in range(number_of_bins):
            if bin_members is not None:
                members = bin_members[i]
            else:
                members = None
            self.bins.append(BinnedScenarioCandidate(bin_variables[i], members=members))

    @property
    def number_of_bins(self):
        return len(self.bins)

    @property
    def number_of_members(self):
        return sum(b.number_of_members for b in self.bins)

    def get_variable_array(self):
        shp = (self.number_of_members, self.number_of_variables)
        a = np.empty(shp)
        for b in self.bins:
            b.populate_variable_array(a)
        return a

    def get_bin_indices_array(self):
        indices = np.empty(self.number_of_members, dtype=np.int32)
        for i, b in enumerate(self.bins):
            for m in b.members:
                indices[m] = i
        return indices

    def update_bin_members(self, ibin, new_members):
        for i, b in enumerate(self.bins):
            if i == ibin:
                b.members = set(new_members)
            else:
                # remove new members from other bins
                for m in b.members.intersection(set(new_members)):
                    b.members.remove(m)

    def assign_missing_members(self, random):
        """ Ensure all members are in at least one group.
        """
        all_assigned_members = [m for b in self.bins for m in b.members]

        for m in self.all_valid_members:
            if m in all_assigned_members:
                continue

            # Member not assigned

            # Select random bin
            ibin = random.randrange(0, self.number_of_bins)
            self.bins[ibin].members.add(m)


class InspyredBinnedOptimisationModel(InspyredOptimisationModel):

    def __init__(self, *args, **kwargs):
        super(InspyredBinnedOptimisationModel, self).__init__(*args, **kwargs)
        # default MetaRecorder to return when evaluating a solution
        self._meta_recorder = MetaRecorder(self)

    def _cache_variable_parameters(self):
        variables = []
        variable_map = [0, ]

        binned_variables = []
        binned_variable_map = [0, ]

        binned_scenario_parameter = None

        for node in self.nodes:
            for var in node.variables:
                if isinstance(var, BinnedScenarioParameter):
                    if binned_scenario_parameter is not None and binned_scenario_parameter != var:
                        raise RuntimeError('Only a single BinnedScenarioParameter can be defined in an optimisation model.')
                    binned_scenario_parameter = var
                elif isinstance(var, BinnedParameter):
                    if var not in binned_variables:
                        binned_variable_map.append(binned_variable_map[-1]+var.size)
                        binned_variables.append(var)
                else:
                    if var not in variables:
                        variable_map.append(variable_map[-1]+var.size)
                        variables.append(var)

        if binned_scenario_parameter is None:
            raise RuntimeError('No BinnedScenarioParameter defined as a variable.')

        self._variables = variables
        self._variable_map = variable_map
        self._binned_variables = binned_variables
        self._binned_variable_map = binned_variable_map
        self._binned_scenario_parameter = binned_scenario_parameter
        print(variables, binned_variables)

    def generator(self, random, args):
        nbins = self._binned_scenario_parameter.number_of_bins
        nscenarios = self._binned_scenario_parameter.scenario.size

        # Initial random bin members
        bin_members = [[] for i in range(nbins)]
        for i in range(nscenarios):
            # Generate initial bin membership
            ibin = random.randint(0, nbins - 1)
            bin_members[ibin].append(i)

        bin_variables = []
        for ibin in range(nbins):
            # Generate initial random variables for this bin
            values = []
            for var in self._binned_variables:
                p = var.parameters[ibin]
                l, u = p.lower_bounds(), p.upper_bounds()
                for i in range(p.size):
                    values.append(random.uniform(l[i], u[i]))
            bin_variables.append(values)

        return MultiBinCandidate(nbins, bin_variables=bin_variables, bin_members=bin_members)

    def evaluator(self, candidates, args):
        fitness = []
        for i, candidate in enumerate(candidates):
            var_meta = {}

            # First update the bin members

            indices = candidate.get_bin_indices_array()
            self._binned_scenario_parameter.update_indices(indices)
            var_meta[self._binned_scenario_parameter.name] = {
                '__class__': self._binned_scenario_parameter.__class__.__name__,
                'values': list(indices)
            }

            # Second update the binned variables
            for ivar, var in enumerate(self._binned_variables):
                bins_meta = []
                j = slice(self._binned_variable_map[ivar], self._binned_variable_map[ivar + 1])

                for ibin, bin in enumerate(candidate.bins):

                    p = var.parameters[ibin]
                    p.update(bin.variables[j])

                    bins_meta.append({
                        'name': p.name, '__class__': p.__class__.__name__,
                        'values': bin.variables[j]
                    })
                var_meta[var.name] = {
                    '__class__': var.__class__.__name__,
                    'binned': True,
                    'parameters': bins_meta
                }

            self.reset()
            self.run()

            fit = inspyred.ec.emo.Pareto([r.aggregated_value() for r in self._objectives])
            fit.meta = {'variables': var_meta, 'objectives': self._meta_recorder.value()}
            fitness.append(fit)
            print(fitness[-1])

        return fitness

    def bounder(self, candidate, args):
        for ivar, var in enumerate(self._binned_variables):
            j = slice(self._binned_variable_map[ivar], self._binned_variable_map[ivar + 1])
            for ibin, bin in enumerate(candidate.bins):
                p = var.parameters[ibin]
                # Ensure all bins are within bounds
                bin.variables[j] = np.minimum(p.upper_bounds(), np.maximum(p.lower_bounds(), bin.variables[j]))
        return candidate

    def observer(self, population, num_generations, num_evaluations, args):
        print(num_generations, num_evaluations, )
        import json

        class NumpyEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, np.integer):
                    return int(obj)
                elif isinstance(obj, np.floating):
                    return float(obj)
                elif isinstance(obj, np.ndarray):
                    return obj.tolist()
                else:
                    return super(NumpyEncoder, self).default(obj)

        archive_filename = args.get('archive_filename')
        with open(archive_filename, mode='w') as fh:
            json.dump([p.fitness.meta for p in population], fh, sort_keys=True, indent=4, separators=(',', ': '),
                      cls=NumpyEncoder)


def null_bounder(candidate, args):
    return candidate


@inspyred.ec.variators.mutator
def binned_variable_gaussian_mutation(random, candidate, args):
    new = copy.deepcopy(candidate)

    bounder = args['_ec'].bounder
    args['_ec'].bounder = null_bounder

    for bold, bnew in zip(candidate.bins, new.bins):
        a = bold.variables
        mutated = inspyred.ec.variators.gaussian_mutation.single_mutation(random, a, args)
        bnew.variables = mutated

    new = bounder(new, args)
    args['_ec'].bounder = bounder
    return new


@inspyred.ec.variators.crossover
def binned_variable_blend_crossover(random, mom, dad, args):
    bro = copy.deepcopy(mom)
    sis = copy.deepcopy(dad)

    bounder = args['_ec'].bounder
    args['_ec'].bounder = null_bounder

    for b_mom, b_dad, b_bro, b_sis in zip(mom.bins, dad.bins, bro.bins, sis.bins):
        a, b = inspyred.ec.variators.blend_crossover.single_crossover(random, b_mom.variables, b_dad.variables, args)

        b_bro.variables = a
        b_sis.variables = b

    bro = bounder(bro, args)
    sis = bounder(sis, args)
    args['_ec'].bounder = bounder

    return [bro, sis]


@inspyred.ec.variators.crossover
def bin_crossover(random, mom, dad, args):
    crossover_rate = args.setdefault('crossover_rate', 1.0)
    num_crossover_points = args.setdefault('num_crossover_points', 1)
    children = []
    if random.random() < crossover_rate:
        nbins = mom.number_of_bins

        num_cuts = min(nbins - 1, num_crossover_points)
        cut_points = random.sample(range(1, nbins), num_cuts)
        cut_points.sort()

        bro = copy.deepcopy(dad)
        sis = copy.deepcopy(mom)

        # print('Crossover: npoints: {:d}, cut_points: {}'.format(num_cuts, cut_points))

        # Perform the cross over by swapping bin sets
        normal = True
        for i, (b_mom, b_dad) in enumerate(zip(mom.bins, dad.bins)):
            if i in cut_points:
                normal = not normal

            if not normal:
                # Cross over the members of the bins
                bro.update_bin_members(i, copy.copy(b_mom.members))
                sis.update_bin_members(i, copy.copy(b_dad.members))
                # Also crossover the variables
                bro.bins[i].variables = b_mom.variables.copy()
                sis.bins[i].variables = b_dad.variables.copy()
                normal = not normal

        # Reconcile any missing members
        bro.assign_missing_members(random)
        sis.assign_missing_members(random)

        # Ensure we still have the same number of members
        assert bro.number_of_members == dad.number_of_members
        assert sis.number_of_members == dad.number_of_members

        children.append(bro)
        children.append(sis)

    return children


@inspyred.ec.variators.mutator
def bin_mutation(random, candidate, args):
    rate = args.setdefault('mutation_rate', 0.1)

    if random.random() < rate:
        size = candidate.number_of_bins
        # Select two random bins
        p = random.randint(0, size - 1)
        q = random.randint(0, size - 1)
        if p == q:
            return candidate

        try:
            p_member = random.choice(list(candidate.bins[p].members))
        except IndexError:
            p_member = None
        try:
            q_member = random.choice(list(candidate.bins[q].members))
        except IndexError:
            q_member = None

        if p_member is None and q_member is None:
            return candidate

        new = copy.deepcopy(candidate)
        # Swap p and q on new copy
        if p_member is not None:
            new.bins[p].members.remove(p_member)
            new.bins[q].members.add(p_member)
        if q_member is not None:
            new.bins[p].members.add(q_member)
            new.bins[q].members.remove(q_member)

        return new
    else:
        return candidate

