from pywr._core cimport Scenario, ScenarioIndex, Timestep
from pywr.parameters._parameters cimport Parameter, IndexParameter


cdef class BinnedScenarioParameter(IndexParameter):
    cdef int[:] _bin_indices
    cdef public Scenario scenario
    cdef public int number_of_bins
    cdef int _scenario_index
    cdef double[:] _lower_bounds
    cdef double[:] _upper_bounds
    cpdef update_indices(self, int[:] values)

cdef class BinnedParameter(IndexParameter):
    cdef public BinnedScenarioParameter binned_scenario_parameter
    cdef public list parameters