from pywr._core cimport Scenario, ScenarioIndex, Timestep
from pywr.parameters._parameters cimport Parameter, IndexParameter
import numpy as np
cimport numpy as np


cdef class BinnedScenarioParameter(IndexParameter):
    def __init__(self, Scenario scenario, **kwargs):
        self.scenario = scenario
        self.size = scenario.size
        self.number_of_bins = kwargs.pop('number_of_bins', 1)

        super(BinnedScenarioParameter, self).__init__(**kwargs)

    property bin_indices:
        def __get__(self):
            return np.array(self._bin_indices)

    cpdef setup(self, model):
        self._bin_indices = np.zeros(self.scenario.size, dtype=np.int32)
        self._scenario_index = model.scenarios.get_scenario_index(self.scenario)
        # Pre-calculate bounds
        self._lower_bounds = np.ones(self.size) * 0
        self._upper_bounds = np.ones(self.size) * self.number_of_bins

    cpdef int index(self, Timestep timestep, ScenarioIndex scenario_index) except? -1:
        # This is the index of the member of this scenario in the current ScenarioIndex object
        cdef int i = scenario_index._indices[self._scenario_index]
        # return current bin number of this member
        return self._bin_indices[i]

    cpdef update_indices(self, int[:] values):
        cdef int i
        cdef int mx = self.number_of_bins - 1

        if np.min(values) < 0:
            raise ValueError('At least one bin index less than zero.')
        if np.max(values) > mx:
            raise ValueError('At least one bin index greater than maximum value.')
        self._bin_indices = values


    cpdef double[:] lower_bounds(self):
        return np.array(self._lower_bounds)

    cpdef double[:] upper_bounds(self):
        return np.array(self._upper_bounds)


cdef class BinnedParameter(IndexParameter):
    """Wrapper for Parameters which caches the result"""
    def __init__(self, binned_scenario_parameter, parameters, *args, **kwargs):
        super(BinnedParameter, self).__init__(*args, **kwargs)
        self.binned_scenario_parameter = binned_scenario_parameter
        self.children.add(binned_scenario_parameter)
        self.parameters = []
        for p in parameters:
            self.parameters.append(p)
            self.children.add(p)
        # TODO enforce this for all parameters
        self.size = self.parameters[0].size

    cpdef double value(self, Timestep timestep, ScenarioIndex scenario_index) except? -1:
        cdef int i = self.binned_scenario_parameter.index(timestep, scenario_index)
        return self.parameters[i].value(timestep, scenario_index)

    cpdef int index(self, Timestep timestep, ScenarioIndex scenario_index) except? -1:
        cdef int i = self.binned_scenario_parameter.index(timestep, scenario_index)
        return self.parameters[i].index(timestep, scenario_index)

    @classmethod
    def load(cls, model, data):
        raise NotImplementedError()


