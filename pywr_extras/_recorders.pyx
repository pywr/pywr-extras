from pywr._recorders cimport ParameterRecorder, Recorder
from pywr.parameters._parameters cimport ConstantParameter
from ._optimisation cimport BinnedScenarioParameter
import numpy as np
cimport numpy as np


cdef class ConstantParameterScaledRecorder(ParameterRecorder):
    cdef ConstantParameter _cparam
    cdef double[:] x, y
    """Records the mean value of a Parameter for the last N timesteps"""
    def __init__(self, model, param, x, y, *args, **kwargs):
        super(ConstantParameterScaledRecorder, self).__init__(model, param, *args, **kwargs)
        self._cparam = param

        self.x = x
        self.y = y

    cpdef double[:] values(self):
        cdef double v = self._cparam._value
        cdef double c = np.interp(v, self.x, self.y)
        return np.ones(len(self.model.scenarios.combinations)) * c


cdef class BinnedRecorder(Recorder):
    cdef public BinnedScenarioParameter binned_scenario_parameter
    cdef public list recorders

    """Wrapper for Parameters which caches the result"""
    def __init__(self, model, binned_scenario_parameter, recorders, *args, **kwargs):
        super(BinnedRecorder, self).__init__(model, *args, **kwargs)
        self.binned_scenario_parameter = binned_scenario_parameter
        self.recorders = [r for r in recorders]

    cpdef double[:] values(self):

        cdef Recorder r
        cdef int i
        cdef int[:] indices = self.binned_scenario_parameter._bin_indices
        cdef int n = len(self.model.scenarios.combinations)
        cdef int m = len(self.recorders)

        cdef double[:, :] values = np.empty((m, n))
        for i, r in enumerate(self.recorders):
            values[i, :] = r.values()
        return np.choose(np.array(indices), np.array(values))