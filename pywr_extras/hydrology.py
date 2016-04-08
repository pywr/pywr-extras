import numpy as np
import os
from pycatchmod.utils import catchment_from_json
from ._hydrology import CatchmodParameter


def create_catchmod_parameter(catchment_name, weather_scenario, climate_change_scenario):
    """


    """
    n = climate_change_scenario.size*weather_scenario.size
    C = catchment_from_json(os.path.join('data', 'catchmod', '{}.json'.format(catchment_name.lower())), n=n)

    from .data import load_catchmod_2000yr_inputs, load_climate_change_factors
    rainfall, pet = load_catchmod_2000yr_inputs(os.path.join('data', '2000yr', 'Inputs',
                                                             '{} 2000yr inputs_Final.csv'.format(catchment_name)))

    if climate_change_scenario.size > 1:
        # Load actual factors
        rainfall_factors, pet_factors = load_climate_change_factors()
        rainfall_factors, pet_factors = rainfall_factors.values.T, pet_factors.values.T
    else:
        rainfall_factors = np.ones((12, 1))
        pet_factors = np.ones_like(rainfall_factors)

    return CatchmodParameter(C, weather_scenario, climate_change_scenario, rainfall.values, pet.values,
                             rainfall_factors, pet_factors)





