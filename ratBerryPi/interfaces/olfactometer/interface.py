from ratBerryPi.interfaces.base import BaseInterface
from pathlib import Path
from ratBerryPi.resources import Valve
import alicat
import asyncio
import time


class Olfactometer(BaseInterface):
    """
    An interface for controlling the olfactometer

    ...

    Attributes:

    flowrate: float
    units: str
    odor_flow_controller_units: str
    dilutant_flow_controller_units: str
    inert_flow_controller_units: str

    odor_flow_controller_max: float
    dilutant_flow_controller_max: float
    inert_flow_controller_max: float

    odor_concentration: float
    odor_valves: Dict[str, Valve]
    odor_valve_states: Dict[str, bool]
    outlet_valve: Valve
    release_valve: Valve


    Methods:

    set_odor_concentration(odor_concentration)
    set_flowrate(flowrate)
    prep_odors(odors, wait_time, odors_present_ok)
    clear_mixing_manifold(wait_time)
    toggle_odor_valve(odor, open_valve, force)
    toggle_outlet_valve(open_valve, force)
    release_odor()
    switch_to_exhaust()
    set_flowrate
    """

    FLOWRATE_UNIT_CONVERSIONS = {
        'LPM': 1,
        'CC': 1000
    }


    def __init__(self, on, config_file =  Path(__file__).parent/"config.yaml", units = 'LPM'):
        super(Olfactometer, self).__init__(on, config_file)

        # create valves
        self.odor_valves = {k: Valve(k + "_valve", self, v) for k,v in self.config["odor_valves"].items()}
        self.outlet_valve = Valve("outlet_valve", self, self.config["outlet_valve"], NC = False)
        self.release_valve = Valve("release_valve", self, self.config["release_valve"])

        # set the units
        self.units = units
        self.odor_flow_controller_units = self.config['odor_flow_controller_units']
        self.dilutant_flow_controller_units = self.config['dilutant_flow_controller_units']
        self.inert_flow_controller_units = self.config['inert_flow_controller_units']

        # get the max flow rates
        self.odor_flow_controller_max = self.config['odor_flow_controller_max']
        self.dilutant_flow_controller_max = self.config['dilutant_flow_controller_max']
        self.inert_flow_controller_max = self.config['inert_flow_controller_max']

        async def _get_controllers():
            self.odor_flow_controller = alicat.FlowController(unit = self.config["odor_flow_controller"])
            self.dilutant_flow_controller = alicat.FlowController(unit = self.config["dilutant_flow_controller"])
            self.inert_flow_controller = alicat.FlowController(unit = self.config["inert_flow_controller"])

            await self.odor_flow_controller.set_gas("Air")
            await self.dilutant_flow_controller.set_gas("Air")
            await self.inert_flow_controller.set_gas("Air")
        
        asyncio.run(_get_controllers())

        self.odor_concentration= self.config["initial_odor_concentration"]
        self.flowrate = self.config["initial_flowrate"]

    @property
    def flowrate(self) -> float:
        """
        get or set the flowrate. setting the flowrate will automatically update
        the flowrate settings on all flow controllers according to the new flowrate
        and already set odor concentration. the odor concentration must be set before
        flowrate can be set
        """
        return self._flowrate
    
    @flowrate.setter
    def flowrate(self, flowrate) -> None:
        assert self._validate_flowrate(flowrate), "flowrate requires at least one flow controller to go out of it's range of operation"
        self.logger.info(f'setting flowrate to {flowrate}')
        self._flowrate = flowrate
        asyncio.run(self._set_controller_flowrates())

    @property
    def odor_concentration(self) -> float:
        """
        get or set the odor concentration. setting the odor concentration will automatically update
        the flowrate settings on all flow controllers according to the new odor concentration
        if a flowrate has already been specified
        """
        return self._odor_concentration
    
    @odor_concentration.setter
    def odor_concentration(self, odor_concentration) -> None:
        if hasattr(self, '_flowrate'):
            assert self._validate_flowrate(self.flowrate, odor_concentration),"odor concentration requires at least one flow controller to go out of it's range of operation"
        self.logger.info(f'setting odor concentration to {odor_concentration}')
        self._odor_concentration = odor_concentration 
        if hasattr(self, '_flowrate'):
            asyncio.run(self._set_controller_flowrates())
    
    @property
    def odor_valve_states(self):
        """
        get the state of all odor valves (i.e. if the valves are open)
        """
        return {k: v.is_open for k,v in self.odor_valves.items()}

    @property
    def units(self):
        """
        a common flow rate unit
        """
        return self._units 
    
    @units.setter
    def units(self, units):
        assert units in self.FLOWRATE_UNIT_CONVERSIONS, 'unrecognized unit'
        self._units = units

    def _validate_flowrate(self, flowrate: float, odor_concentration = None) -> None:
        """
        validate the flow rate
        """
        if not odor_concentration:
            odor_concentration = self.odor_concentration
        valid_flowrate = (self._convert_flowrate(flowrate, self.inert_flow_controller_units)<=self.inert_flow_controller_max) &\
                         (self._convert_flowrate(flowrate * odor_concentration, self.odor_flow_controller_units)<=self.odor_flow_controller_max) &\
                         (self._convert_flowrate(flowrate * (1-odor_concentration), self.dilutant_flow_controller_units)<=self.dilutant_flow_controller_max)
        return valid_flowrate
    def _convert_flowrate(self, flow_rate: float, to_units: str, from_units: str = None) -> None:
        """
        convert flow rate to new units
        """
        from_units = self.units if not from_units else from_units
        return flow_rate * self.FLOWRATE_UNIT_CONVERSIONS[to_units]/self.FLOWRATE_UNIT_CONVERSIONS[from_units]

    def change_units(self, units: str) -> None:
        """
        change the units that flowrates are expressed in
        """
        self.units = units
        
    def set_odor_concentration(self, odor_concentration: float) -> None:
        """
        convenience function for setting the odor concentration

        Args:
            odor_concentration: float
                target odor fractional odor concentration 
        """
        if not 0<=odor_concentration<=1:
            raise ValueError("argument 'odor_concentration' must be a value from 0-1")
        self.odor_concentration = odor_concentration

    def set_flowrate(self, flowrate: float) -> None:
        """
        convenience function for setting the total flowrate

        Args:
            flowrate: float
                target flowrate in units specified at time of purchase of the controller
        """
        self.flowrate = flowrate

    async def _set_controller_flowrates(self) -> None:
        """
        set the flowrates on all mass flow controllers
        to the appropriate values
        """
        inert_flowrate = self._convert_flowrate(self.flowrate, self.inert_flow_controller_units)
        dilutant_flowrate = self._convert_flowrate(self.flowrate * (1-self.odor_concentration), 
                                                   self.dilutant_flow_controller_units)
        odor_flowrate = self._convert_flowrate(self.flowrate * self.odor_concentration, 
                                               self.odor_flow_controller_units)

        await self.inert_flow_controller.set_flow_rate(inert_flowrate)
        await self.dilutant_flow_controller.set_flow_rate(dilutant_flowrate)
        await self.odor_flow_controller.set_flow_rate(odor_flowrate)

    def prep_odors(self, odors, wait_time: float = 1, odors_present_ok: bool = False) -> None:
        """
        open the appropriate valves to allow the odor to flow to
        the mixing manifold

        Args:
            odors: list
                list of odors to prep
            wait_time: float, optional
                time in seconds to wait after opening odor valves
                before closing the outlet valve (default is 1)
            odors_present_ok: bool, optional
                whether or not it's ok to prepare the new odors
                if some odors are already in the mixing manifold
                (default is False)
        """
        assert len(odors)>0, "no odors specified"
        if not odors_present_ok:
            if any([v for k,v in self.odor_valve_states.items() if k not in odors]):
                raise Exception("at least 1 odor valve is already open, if this is ok instead set 'odors_present_ok' to True when calling this function")
        
        self.logger.info(f"preparing odors {';'.join(odors)}")
        for odor in odors: 
            self.toggle_odor_valve(odor, open_valve = True)
        time.sleep(wait_time)
        self.toggle_outlet_valve(open_valve=False)

    def clear_mixing_manifold(self, wait_time:float = 1) -> None:
        """
        clear the mixing manifold of any odors

        Args:
            wait_time: float, optional
                time in seconds to wait after opening the outlet valve
                before closing the odor valves (default is 1)
        """
        self.logger.info(f"clearing the mixing manifold")
        self.toggle_outlet_valve(open_valve=True)
        time.sleep(wait_time)
        for odor in self.odor_valves:
            self.toggle_odor_valve(odor, open_valve = False)

    def toggle_odor_valve(self, odor, open_valve:bool = True, force = False):
        """
        toggles a specified odor valve. if closing the valve
        checks the state of the outlet valve and other odor valves
        to ensure there is a path for air if the valve is closed

        Args:
            odor: str
                odor whose corresponding valve should be toggled
            open_valve: bool, optional
                whether to open the valve (default is True)
        """
        if open_valve:
            self.odor_valves[odor].open()
        else:
            if (not force) and (not self.outlet_valve.is_open) and (not any([v for k,v in self.odor_valve_states.items() if k!=odor])):
                raise Exception("no alternative air paths, cannot close outlet valve")
            self.odor_valves[odor].close()

    def toggle_outlet_valve(self, open_valve = True, force = False):
        """
        toggles the outlet valve. if closing the valve
        checks the state of the outlet valve and other odor valves
        to ensure there is a path for air if the valve is close

        Args:
            open_valve: bool, optional
                whether to open the valve (default is True)
        """
        if open_valve:
            self.outlet_valve.open()
        else:
            if (not any(list(self.odor_valve_states.values()))) and (not force):
                raise Exception("no alternative air paths, cannot close outlet valve")
            self.outlet_valve.close()


    def release_odor(self) -> None:
        """
        switch the final valve to allow odor flow to
        the mask and inert air to flow to the exhaust
        """
        self.logger.info(f"releasing the odor")
        self.release_valve.open()

    def switch_to_exhaust(self) -> None:
        """
        switch the final valve to direct odor flow to
        the exhaust and inert air flow to the mask
        """
        self.logger.info(f"switching odor flow to exhaust")
        self.release_valve.close()