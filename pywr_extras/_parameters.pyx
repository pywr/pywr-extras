from pywr._core cimport Timestep, ScenarioIndex
from pywr.parameters._parameters cimport ConstantParameter
import numpy as np
cimport numpy as np


cdef class ConstantScaledParameter(ConstantParameter):
    cdef public double scale
    def __init__(self, value, scale=1.0, lower_bounds=0.0, upper_bounds=np.inf, **kwargs):
        super(ConstantParameter, self).__init__(**kwargs)
        self._value = value
        self.scale = scale
        self.size = 1
        self._lower_bounds = np.ones(self.size) * lower_bounds
        self._upper_bounds = np.ones(self.size) * upper_bounds

    cpdef double value(self, Timestep ts, ScenarioIndex scenario_index) except? -1:
        return self._value*self.scale