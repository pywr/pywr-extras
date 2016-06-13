from pywr._core cimport Timestep, ScenarioIndex, Scenario
from pywr.parameters._parameters cimport Parameter
from pycatchmod._catchmod cimport Catchment, OudinCatchment
import numpy as np
cimport numpy as np

cdef outer(double[:] a, double[:] b, double[:] c):
    cdef int i, j, m, n
    m = a.shape[0]
    n = b.shape[0]

    for i in range(m):
        for j in range(n):
            c[i*n+j] = a[i]*b[j]


cdef class CatchmodParameter(Parameter):
    """ A parameter that returns the flow from a pycatchmod.Catchment model

    This parameter is index based on the input rainfall and pet values.

    """
    cdef int _scenario_index
    cdef int _cc_scenario_index
    cdef int _prev_index
    cdef int _timestep
    cdef double[:, :] outflow
    cdef double[:] total_outflow
    cdef double[:, :] percolation
    cdef double[:] _perturbed_rainfall
    cdef double[:] _perturbed_pet
    cdef double[:, :] rainfall
    cdef double[:, :] rainfall_factors
    cdef double[:, :] pet
    cdef double[:, :] pet_factors
    cdef Scenario scenario
    cdef Scenario climate_change_scenario
    cdef Catchment catchmod

    def __init__(self, catchmod, scenario, climate_change_scenario, rainfall, pet,
                 rainfall_factors, pet_factors, *args, **kwargs):
        super(CatchmodParameter, self).__init__(*args, **kwargs)

        if scenario.size*climate_change_scenario.size != catchmod.size:
            raise ValueError("The size of the catchmod model must be the same as the product of the weather and"
                             " climate change scenarios.")
        if scenario.size != rainfall.shape[1]:
            raise ValueError("Rainfall data must be the same shape as the weather scenario.")
        if scenario.size != pet.shape[1]:
            raise ValueError("PET data must be the same shape as the weather scenario.")
        if climate_change_scenario.size != rainfall_factors.shape[1]:
            raise ValueError("Rainfall factors must be the same shape as the climate change scenario.")
        if climate_change_scenario.size != pet_factors.shape[1]:
            raise ValueError("PET factors must be the same shape as the climate change scenario.")

        self.scenario = scenario
        self.climate_change_scenario = climate_change_scenario
        self.catchmod = catchmod
        self.rainfall = rainfall
        self.rainfall_factors = rainfall_factors
        self.pet_factors = pet_factors
        self.pet = pet
        self._prev_index = -1

    cpdef setup(self, model):
        # Store the model's timestep locally.
        self._timestep = model.timestepper.delta.days

        # This setup must find out the index of self._scenario in the model
        # so that it can return the correct value in value()
        self._scenario_index = model.scenarios.get_scenario_index(self.scenario)
        self._cc_scenario_index = model.scenarios.get_scenario_index(self.climate_change_scenario)

        # Array to store the outflow results at each timestep
        nsubs = len(self.catchmod.subcatchments)
        self.outflow = np.empty((nsubs, self.catchmod.size))
        self.total_outflow = np.empty(self.catchmod.size)
        self.percolation = np.empty((nsubs, self.catchmod.size))
        self._prev_index = -1
        # work arrays for computing outer product of rainfall/pet with climate change factors
        self._perturbed_rainfall = np.empty(self.scenario.size*self.climate_change_scenario.size)
        self._perturbed_pet = np.empty_like(self._perturbed_rainfall)

    cpdef before(self, Timestep ts):
        # Step the catchmod model forward
        cdef int index, i, j, k, m
        cdef double flow
        if ts._index != self._prev_index:
            for j in range(self.total_outflow.shape[0]):
                self.total_outflow[j] = 0.0

            # Catchmod must run daily. So if a non-daily timestep is used we still simulate catchmod at
            # a daily level and simply average the results.

            # TODO month is the month at the end of the timestep. It does not vary through the subdaily timesteps
            m = ts.datetime.month - 1
            for i in range(self._timestep):
                index = ts.index*self._timestep + i
                # Compute perturbed rainfall/pet by multiplying by climate change factors
                outer(self.rainfall[index, :], self.rainfall_factors[m, :], self._perturbed_rainfall)
                outer(self.pet[index, :], self.pet_factors[m, :], self._perturbed_pet)

                self.catchmod.step(self._perturbed_rainfall, self._perturbed_pet, self.percolation, self.outflow)
                # Total the outflow from the subcatchments and average over the timesteps
                for j in range(self.total_outflow.shape[0]):
                    # Sum the total flow across all subcatchments for index j
                    flow = 0.0
                    for k in range(self.outflow.shape[0]):
                        flow += self.outflow[k, j]
                    # Add to the total flow variable
                    # TODO it might be marginally more efficient to do these divisions once at the end.
                    self.total_outflow[j] += flow/86.4/self._timestep
            self._prev_index = ts.index

    cpdef double value(self, Timestep ts, ScenarioIndex scenario_index) except? -1:
        cdef int i = scenario_index._indices[self._scenario_index]
        cdef int n = self.climate_change_scenario._size
        cdef int j = scenario_index._indices[self._cc_scenario_index]
        return self.total_outflow[i*n+j]


cdef class OudinCatchmodParameter(Parameter):
    """ A parameter that returns the flow from a pycatchmod.Catchment model

    This parameter is index based on the input rainfall and pet values.

    """
    cdef int _scenario_index
    cdef int _cc_scenario_index
    cdef int _prev_index
    cdef int _timestep
    cdef double[:, :] outflow
    cdef double[:] total_outflow
    cdef double[:, :] percolation
    cdef double[:] _perturbed_rainfall
    cdef double[:] _perturbed_temp
    cdef double[:, :] rainfall
    cdef double[:, :] rainfall_factors
    cdef double[:, :] temp
    cdef double[:, :] temp_factors
    cdef double[:] pet
    cdef Scenario scenario
    cdef Scenario climate_change_scenario
    cdef OudinCatchment catchmod

    def __init__(self, catchmod, scenario, climate_change_scenario, rainfall, temperature,
                 rainfall_factors, temperature_factors, *args, **kwargs):
        super(OudinCatchmodParameter, self).__init__(*args, **kwargs)

        if scenario.size*climate_change_scenario.size != catchmod.size:
            raise ValueError("The size of the catchmod model must be the same as the product of the weather and"
                             " climate change scenarios.")
        if scenario.size != rainfall.shape[1]:
            raise ValueError("Rainfall data must be the same shape as the weather scenario.")
        if scenario.size != temperature.shape[1]:
            raise ValueError("Temperature data must be the same shape as the weather scenario.")
        if climate_change_scenario.size != rainfall_factors.shape[1]:
            raise ValueError("Rainfall factors must be the same shape as the climate change scenario.")
        if climate_change_scenario.size != temperature_factors.shape[1]:
            raise ValueError("Temperature factors must be the same shape as the climate change scenario.")

        self.scenario = scenario
        self.climate_change_scenario = climate_change_scenario
        self.catchmod = catchmod
        self.rainfall = rainfall
        self.rainfall_factors = rainfall_factors
        self.temp_factors = temperature_factors
        self.temp = temperature
        self._prev_index = -1

    cpdef setup(self, model):
        # Store the model's timestep locally.
        self._timestep = model.timestepper.delta.days

        # This setup must find out the index of self._scenario in the model
        # so that it can return the correct value in value()
        self._scenario_index = model.scenarios.get_scenario_index(self.scenario)
        self._cc_scenario_index = model.scenarios.get_scenario_index(self.climate_change_scenario)

        # Array to store the outflow results at each timestep
        nsubs = len(self.catchmod.subcatchments)
        self.outflow = np.empty((nsubs, self.catchmod.size))
        self.total_outflow = np.empty(self.catchmod.size)
        self.pet = np.empty(self.catchmod.size)
        self.percolation = np.empty((nsubs, self.catchmod.size))

        self._prev_index = -1
        # work arrays for computing outer product of rainfall/pet with climate change factors
        self._perturbed_rainfall = np.empty(self.scenario.size*self.climate_change_scenario.size)
        self._perturbed_temp = np.empty_like(self._perturbed_rainfall)

    cpdef before(self, Timestep ts):
        # Step the catchmod model forward
        cdef int index, i, j, k, m, doy, nt
        cdef double flow
        if ts._index != self._prev_index:
            for j in range(self.total_outflow.shape[0]):
                self.total_outflow[j] = 0.0

            # Catchmod must run daily. So if a non-daily timestep is used we still simulate catchmod at
            # a daily level and simply average the results.

            # TODO month is the month at the end of the timestep. It does not vary through the subdaily timesteps
            m = ts.datetime.month - 1
            nt = 0
            for i in range(self._timestep):
                index = ts.index*self._timestep + i

                if i > 0 and (index >= self.rainfall.shape[0] or index >= self.temp.shape[0]):
                    break

                doy = ts.datetime.dayofyear - self._timestep + i + 1
                # Compute perturbed rainfall/temperature by multiplying by climate change factors

                outer(self.rainfall[index, :], self.rainfall_factors[m, :], self._perturbed_rainfall)
                outer(self.temp[index, :], self.temp_factors[m, :], self._perturbed_temp)

                self.catchmod.step(doy, self._perturbed_rainfall, self._perturbed_temp, self.pet, self.percolation, self.outflow)
                # Total the outflow from the subcatchments and average over the timesteps
                for j in range(self.total_outflow.shape[0]):
                    # Sum the total flow across all subcatchments for index j
                    flow = 0.0
                    for k in range(self.outflow.shape[0]):
                        flow += self.outflow[k, j]
                    # Add to the total flow variable
                    self.total_outflow[j] += flow
                nt += 1
            # Average flow over simulated timesteps and convert to Ml/d from m3/s
            for j in range(self.total_outflow.shape[0]):
                self.total_outflow[j] /= 86.4*nt

            self._prev_index = ts.index

    cpdef double value(self, Timestep ts, ScenarioIndex scenario_index) except? -1:
        cdef int i = scenario_index._indices[self._scenario_index]
        cdef int n = self.climate_change_scenario._size
        cdef int j = scenario_index._indices[self._cc_scenario_index]
        return self.total_outflow[i*n+j]