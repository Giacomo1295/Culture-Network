"""Define individual agent class
A module that defines "individuals" that have vectors of attitudes towards behaviours whose evolution
is determined through weighted social interactions.



Created: 10/10/2022
"""

# imports
import numpy as np
import numpy.typing as npt

rng = np.random.default_rng(42)


# modules
class Individual:

    """
    Class to represent individuals with identities and behaviours

    ...

    Attributes
    ----------

    save_timeseries_data : bool
        whether or not to save data. Set to 0 if only interested in end state of the simulation. If 1 will save
        data into timeseries.
    compression_factor: int
        how often data is saved. If set to 1 its every step, then 10 is every 10th steps. Higher value gives lower
        resolution for graphs but more managable saved or end object size
    t: float
        keep track of time
    M: int
        number of behaviours per individual. These behaviours are meant to represent action decisions that operate under the
        same identity such as the decision to cycle to work or take the car.
    phi_array: npt.NDArray[float]
        list of degree of social susceptibility or conspicous consumption of the different behaviours.
    values: npt.NDArray[float]
        array containing behavioural values, if greater than 0 then the green alternative behaviour is performed and emissions from that behaviour are 0. Domain =  [-1,1]
    av_behaviour_attitude
        mean attitude towards M behaviours at time t
    av_behaviour_value
        mean value towards M behaviours at time t
    av_behaviour_list: list[float]
        time series of past average attitude combined with values depending on action_observation_I, as far back as cultural_inertia
    identity: float
        identity of the individual, if > 0.5 it is considered green. Determines who individuals pay attention to. Domain = [0,1]
    total_carbon_emissions: float
        total carbon emissions of that individual due to their behaviour
    history_behaviour_values: list[list[float]]
        timeseries of past behavioural values
    history_behaviour_attitudes: list[list[float]]
        timeseries of past behavioural attitudes
    self.history_behaviour_thresholds: list[list[float]]
        timeseries of past behavioural thresholds, static in the current model version
    self.history_av_behaviour: list[float]
        timeseries of past average behavioural attitudes
    self.history_identity: list[float]
        timeseries of past identity values
    self.history_carbon_emissions: list[float]
        timeseries of past individual total emissions

    Methods
    -------
    update_av_behaviour_list():
        Update moving average of past behaviours, inserting present value and 0th index and removing the oldest value
    calc_identity() -> float:
        Calculate the individual identity from past average attitudes weighted by the truncated quasi-hyperbolic discounting factor
    update_values():
        Update the behavioural values of an individual with the new attitudinal or threshold values
    update_attitudes(social_component):
        Update behavioural attitudes with social influence of neighbours mediated by the social susceptabilty of each behaviour phi
    calc_total_emissions_flow():
        return total emissions of individual based on behavioural values
    save_timeseries_data_individual():
        Save time series data
    next_step(t:float, steps:int, social_component: npt.NDArray):
        Push the individual simulation forwards one time step

    """

    def __init__(
        self,
        individual_params,
        init_data_attitudes,
        init_data_thresholds,
        normalized_discount_vector,
        cultural_inertia,
        init_data_pU,
        init_data_pC,
        init_data_pR,
        init_data_thresholdspU,
        init_data_thresholdspC,
        init_data_thresholdspR,
        id_n: int
    ):
        """
        Constructs all the necessary attributes for the Individual object.

        Parameters
        ----------
        individual_params: dict,
            useful parameters from the network
        init_data_attitudes: npt.NDArray[float]
            array of initial attitudes generated previously from a beta distribution, evolves over time
        init_data_thresholds: npt.NDArray[float]
            array of initial thresholds generated previously from a beta distribution
        normalized_discount_vector: npt.NDArray[float]
            normalized single row of the discounts to individual memory when considering how the past influences current identity
        cultural_inertia: int
            the number of steps into the past that are considered when calculating identity

        """

        self.attitudes = init_data_attitudes
        self.initial_first_attitude = (self.attitudes[0]).copy()
        self.thresholds = init_data_thresholds
        self.normalized_discount_vector = normalized_discount_vector
        self.cultural_inertia = cultural_inertia
        self.pU = init_data_pU
        self.pC = init_data_pC
        self.pR = init_data_pR
        self.thresholdspU = init_data_thresholdspU
        self.thresholdspC = init_data_thresholdspC
        self.thresholdspR = init_data_thresholdspR


        self.M = individual_params["M"]
        self.t = individual_params["t"]
        self.save_timeseries_data = individual_params["save_timeseries_data"]
        self.compression_factor = individual_params["compression_factor"]
        self.phi_array = individual_params["phi_array"]
        self.alpha_change = individual_params["alpha_change"]

        self.id = id_n

        self.green_fountain_state = 0

        if self.alpha_change == "behavioural_independence":
            self.attitudes_matrix = np.tile(self.attitudes, (self.cultural_inertia,1))
            self.attitudes_star = self.calc_attitudes_star()

        self.values = self.attitudes - self.thresholds
        self.av_behaviour = np.mean((1 - self.attitudes) ** 2)
        self.av_behaviour_list = [self.av_behaviour] * self.cultural_inertia
        self.identity = self.calc_identity()
        self.initial_carbon_emissions,self.behavioural_carbon_emissions = self.calc_total_emissions_flow()
        self.individual_carbon_emissions_flow = self.initial_carbon_emissions

        if self.save_timeseries_data:
            self.history_behaviour_values = [list(self.values)]
            self.history_behaviour_attitudes = [list(self.attitudes)]
            self.history_behaviour_thresholds = [list(self.thresholds)]
            self.history_TA = [self.TA]
            self.history_thresholdsTA = [self.thresholdsTA]
            self.history_av_behaviour = [self.av_behaviour]
            self.history_identity = [self.identity]
            self.history_individual_carbon_emissions_flow = [self.individual_carbon_emissions_flow]
            self.history_behavioural_carbon_emissions = [self.behavioural_carbon_emissions]

    @property
    def TA(self):
        return 0.7 * self.pU - 0.2 * self.pC - 0.1 * self.pR
    
    @property
    def thresholdsTA(self):
        return 0.7 * self.thresholdspU - 0.2 * self.thresholdspC - 0.1 * self.thresholdspR



    def calc_av_behaviour(self):
        self.av_behaviour = np.mean((1 - self.attitudes) ** 2)

    def update_av_behaviour_list(self):
        """
        Update moving average of past behaviours, inserting present value and 0th index and removing the oldest value

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        self.av_behaviour_list.pop()
        self.av_behaviour_list.insert(0, self.av_behaviour)

    def calc_identity(self) -> float:
        """
        Calculate the individual identity from past average attitudes weighted by the truncated quasi-hyperbolic discounting factor

        Parameters
        ----------
        None

        Returns
        -------
        float
        """

        return np.matmul(
            self.normalized_discount_vector, self.av_behaviour_list
        )  # here discount list is normalized

    def update_attitudes_matrix(self):       
        self.attitudes_matrix =  np.vstack([np.asarray([self.attitudes]), self.attitudes_matrix[:-1,:]])

    def calc_attitudes_star(self):
        return np.matmul(
            self.normalized_discount_vector, self.attitudes_matrix
        )  # here discount list is normalized

    def update_values(self):
        """
        Update the behavioural values of an individual with the new attitudinal or threshold values

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        self.values = 0.5 * (self.attitudes - self.thresholds) + 0.5 * (self.TA - self.thresholdsTA)

    def update_attitudes(self, social_component):
        """
        Update behavioural attitudes with social influence of neighbours mediated by the social susceptabilty of each behaviour phi

        Parameters
        ----------
        social_component: npt.NDArray[float]

        Returns
        -------
        None
        """
        self.attitudes = (1 - self.phi_array)*self.attitudes + (self.phi_array)*(social_component)
        
    def update_pU(self, social_component):
        """
        Update behavioural attitudes with social influence of neighbours mediated by the social susceptabilty of each behaviour phi

        Parameters
        ----------
        social_component: npt.NDArray[float]

        Returns
        -------
        None
        """
        self.pU = (1 - self.phi_array)*self.pU + (self.phi_array)*(social_component)

    def update_pC(self, TA_component):
        """
        Update behavioural attitudes with social influence of neighbours mediated by the social susceptabilty of each behaviour phi

        Parameters
        ----------
        social_component: npt.NDArray[float]

        Returns
        -------
        None
        """
        self.pC = (1 - self.phi_array)*self.pC + (self.phi_array)*(TA_component)

    def update_pR(self, TA_component):
        """
        Update behavioural attitudes with social influence of neighbours mediated by the social susceptabilty of each behaviour phi

        Parameters
        ----------
        social_component: npt.NDArray[float]

        Returns
        -------
        None
        """
        self.pR = (1 - self.phi_array)*self.pR + (self.phi_array)*(TA_component)

    def update_thresholds(self):
        delta_thresholds = rng.normal(loc=0, scale=0.03, size=len(self.thresholds))
        self.thresholds = np.clip(self.thresholds + delta_thresholds, 0, 1)

    def update_thresholdTA (self):
        delta_TA = rng.normal(loc=0, scale=0.03, size=3)
        self.thresholdspU = np.clip(self.thresholdspU + delta_TA[0], 0, 1)
        self.thresholdspC = np.clip(self.thresholdspC + delta_TA[1], 0, 1)
        self.thresholdspR = np.clip(self.thresholdspR + delta_TA[2], 0, 1)

    def calc_total_emissions_flow(self):
        """
        Return total emissions of individual based on behavioural values

        Parameters
        ----------
        None

        Returns
        -------
        float
        """
        behavioural_emissions = [((1-self.values[i])/2) for i in range(self.M)]
        return sum(behavioural_emissions),behavioural_emissions# normalized Beta now used for emissions

    def save_timeseries_data_individual(self):
        """
        Save time series data

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        self.history_behaviour_values.append(list(self.values))
        self.history_behaviour_attitudes.append(list(self.attitudes))
        self.history_behaviour_thresholds.append(list(self.thresholds))
        self.history_TA.append(list(self.TA))
        self.history_identity.append(self.identity)
        self.history_av_behaviour.append(self.av_behaviour)
        self.history_individual_carbon_emissions_flow.append(self.individual_carbon_emissions_flow)
        self.history_behavioural_carbon_emissions.append(self.behavioural_carbon_emissions)

    def next_step(self, t: int, social_component: npt.NDArray, TA_component: tuple[npt.NDArray, npt.NDArray, npt.NDArray]):
        """
        Push the individual simulation forwards one time step. Update time, then behavioural values, attitudes and thresholds then calculate
        new identity of agent and save results.

        Parameters
        ----------
        t: float
            Internal time of the simulation
        social_component: npt.NDArray
            NxM Array of the influence of neighbours from imperfect social learning on behavioural attitudes of the individual
        Returns
        -------
        None
        """
        self.t = t

        TA_component_pU, TA_component_pC, TA_component_pR = TA_component 

        self.update_values()
        self.update_attitudes(social_component)
        self.update_pU(TA_component_pU)
        self.update_pC(TA_component_pC)
        self.update_pR(TA_component_pR)
        

        if self.alpha_change == "behavioural_independence":
            self.update_attitudes_matrix()
            self.attitudes_star = self.calc_attitudes_star()
        else:
            self.update_thresholds()
            self.update_thresholdTA()
            self.calc_av_behaviour()
            self.update_av_behaviour_list()
            self.identity = self.calc_identity()

        self.individual_carbon_emissions_flow, self.behavioural_carbon_emissions = self.calc_total_emissions_flow()

        if (self.save_timeseries_data) and (self.t % self.compression_factor == 0):
            self.save_timeseries_data_individual()