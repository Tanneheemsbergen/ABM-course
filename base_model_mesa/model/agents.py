# Importing necessary libraries
import random
from mesa import Agent
from shapely.geometry import Point
from shapely import contains_xy
import pandas as pd

# Import functions from functions.py
from functions import generate_random_location_within_map_domain, get_flood_depth, calculate_basic_flood_damage
from functions import floodplain_multipolygon


# Define the Households agent class
class Households(Agent):
    """
    An agent representing a household in the model.
    Each household has a flood depth attribute which is randomly assigned for demonstration purposes.
    In a real scenario, this would be based on actual geographical data or more complex logic.
    """

     # Define available flood measures and their costs
    flood_measures = {
        'Sandbags': 5000,
        'Elevating the house': 80000,
        'Relocating electrical systems': 25000
    }

    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.is_adapted = False  # Initial adaptation status set to False
        
        #Assigning random starting wealth to households between 0 and 10000
        self.wealth = random.uniform(0, 10000)
        self.income = random.uniform(0,8000)

        # getting flood map values
        # Get a random location on the map
        loc_x, loc_y = generate_random_location_within_map_domain()
        self.location = Point(loc_x, loc_y)

        # Check whether the location is within floodplain
        self.in_floodplain = False
        if contains_xy(geom=floodplain_multipolygon, x=self.location.x, y=self.location.y):
            self.in_floodplain = True

        # Get the estimated flood depth at those coordinates. 
        # the estimated flood depth is calculated based on the flood map (i.e., past data) so this is not the actual flood depth
        # Flood depth can be negative if the location is at a high elevation
        self.flood_depth_estimated = get_flood_depth(corresponding_map=model.flood_map, location=self.location, band=model.band_flood_img)
        # handle negative values of flood depth
        if self.flood_depth_estimated < 0:
            self.flood_depth_estimated = 0
        
        # calculate the estimated flood damage given the estimated flood depth. Flood damage is a factor between 0 and 1
        self.flood_damage_estimated = calculate_basic_flood_damage(flood_depth=self.flood_depth_estimated)

        # Add an attribute for the actual flood depth. This is set to zero at the beginning of the simulation since there is not flood yet
        # and will update its value when there is a shock (i.e., actual flood). Shock happens at some point during the simulation
        self.flood_depth_actual = 0
        
        #calculate the actual flood damage given the actual flood depth. Flood damage is a factor between 0 and 1
        self.flood_damage_actual = calculate_basic_flood_damage(flood_depth=self.flood_depth_actual)

        self.risk_aversness = random.uniform(0, 1)

        self.adaptation_budget = self.wealth * self.risk_aversness
        print("Budget:",self.adaptation_budget)
        # Selecting a flood measure based on wealth
        affordable_measures = {measure: cost for measure, cost in Households.flood_measures.items() if cost <= self.adaptation_budget}
        if affordable_measures:
            self.selected_measure = max(affordable_measures, key=affordable_measures.get)
        else:
            self.selected_measure = None
       
        # Only increment the counter if selected_measure is not None
        if self.selected_measure is not None:
            self.model.flood_measure_count[self.selected_measure] += 1
        else:
            self.model.flood_measure_count[None] += 1
            
        print('before:',self.flood_damage_estimated )
        print(self.selected_measure)

        # Modify flood damage calculation based on selected measure
        if self.selected_measure is not None:
            # Reduce estimated flood damage based on the measure
            self.flood_damage_estimated *= self.calculate_damage_reduction_factor(self.selected_measure)
            print(self.flood_damage_estimated)
        else:
            # Use existing calculation
            self.flood_damage_estimated = calculate_basic_flood_damage(flood_depth=self.flood_depth_estimated)

    def calculate_damage_reduction_factor(self, measure):
        # Define how different measures reduce flood damage
        reduction_factors = {
            'Sandbags': 0.05,  # Example reduction factor
            'Elevating the house': 0.7,
            'Relocating electrical systems': 0.3
        }
        return reduction_factors.get(measure, 1)  # Default to no reduction if measure is not found
    
    def generate_households_table(model):
    # Generates a table showing each household, their selected flood adaptation measure, and the resulting reduction factor.

        household_data = []

        for household in model.schedule.agents:
            household_info = {
                'Household ID': household.unique_id,
                'Selected Measure': household.selected_measure if household.selected_measure else 'None',
                'Reduction Factor': household.calculate_damage_reduction_factor(household.selected_measure)
            }
        household_data.append(household_info)
        print(household_data)
        return pd.DataFrame(household_data)
    # Function to count friends who can be influencial.
    def count_friends(self, radius):
        """Count the number of neighbors within a given radius (number of edges away). This is social relation and not spatial"""
        friends = self.model.grid.get_neighborhood(self.pos, include_center=False, radius=radius)
        return len(friends)

    def step(self):
        # Logic for adaptation based on estimated flood damage and a random chance.
        # These conditions are examples and should be refined for real-world applications.
         # Re-evaluate adaptation status every step
        self.is_adapted = False  # Reset adaptation status

        # Define a threshold for considering a household adapted
        minimum_damage_threshold = 0.1
        adaptation_threshold = 0.15 # Example

        if self.flood_damage_estimated < minimum_damage_threshold:
                self.is_adapted = True  # Agent adapts to flooding
        else:
        # Check if a flood measure is selected and effective
            if self.selected_measure:
                damage_reduction = self.calculate_damage_reduction_factor(self.selected_measure)
                if damage_reduction >= adaptation_threshold:
                    self.is_adapted = True
        print(self.is_adapted)
       
# Define the Government agent class
class Government(Agent):
    """
    A government agent that have subsidy available
    """
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.subsidy_budget = 40000 # Total subsidy budget available

    def support_non_adapted_households(self):
        # List to store non-adapted households
        non_adapted_households = [household for household in self.model.schedule.agents if isinstance(household, Households) and not household.is_adapted]

        # Print the list of non-adapted households
        print("Non-adapted Households:", non_adapted_households)

        # Print the sum of non-adapted households
        print("Total Non-adapted Households:", len(non_adapted_households))

        # Support households with subsidy
        subsidy_amount = 4000  # Amount of subsidy for each household
        for household in non_adapted_households:
            if household.wealth < 1500 and self.subsidy_budget >= subsidy_amount:
                household.wealth += subsidy_amount
                self.subsidy_budget -= subsidy_amount
                # Re-evaluate adaptation possibility after updating wealth
                self.re_evaluate_adaptation_possibility(household)
                if self.subsidy_budget < subsidy_amount:
                    break  # Stop if the subsidy budget is depleted

        # Print the remaining subsidy budget
        print("Remaining Subsidy Budget:", self.subsidy_budget)

        # Recalculate the sum of non-adapted households
        updated_non_adapted_count = sum(1 for household in self.model.schedule.agents if isinstance(household, Households) and not household.is_adapted)
        
        # Print the updated sum
        print("Updated Total Non-adapted Households:", updated_non_adapted_count)

    def re_evaluate_adaptation_possibility(self, household):
        adaptation_threshold = 5000  # Example threshold value
        if household.wealth >= adaptation_threshold:
            household.is_adapted = True
            # Additional logic to handle adaptation can be added here


    def step(self):
        # The government agent doesn't perform any actions!!.
        pass

# More agent classes can be added here, e.g. ! for insurance agents.
