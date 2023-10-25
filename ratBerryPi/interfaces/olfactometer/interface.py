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
    odor_concentration: float
    odor_valves: Dict[str, Valve]
    odor_valve_states: Dict[str, bool]
    outlet_valve: Valve
    release_valve: Valve


    Methods:

    set_odor_concentration(odor_concentration)
    set_flowrate(flowrate)
    prep_odors(odors, wait_time)
    clear_mixing_manifold(wait_time)
    toggle_odor_valve(odor, open_valve)
    toggle_outlet_valve(open_valve)
    release_odor()
    switch_to_exhaust()
    """

    def __init__(self, on, config_file =  Path(__file__).parent/"config.yaml"):
        super(Olfactometer, self).__init__(on, config_file)

        self.odor_valves = {k: Valve(k + "_valve", self, v) for k,v in self.config["odor_valves"].items()}
        self.outlet_valve = Valve("outlet_valve", self, self.config["outlet_valve"], NC = False)
        self.release_valve = Valve("release_valve", self, self.config["release_valve"])
        
        # self.odor_flow_contrller = alicat.FlowController(self.config["odor_flow_controller"])
        # self.dilutant_flow_contrller = alicat.FlowController(self.config["dilutant_flow_controller"])
        # self.inert_flow_controller = alicat.FlowController(self.config["inert_flow_controller"])

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
        self._odor_concentration = odor_concentration
        if hasattr(self, '_flowrate'):
            asyncio.run(self._set_controller_flowrates())
    
    @property
    def odor_valve_states(self):
        """
        get the state of all odor valves (i.e. if the valves are open)
        """
        return {k: v.is_open for k,v in self.odor_valves.items()}

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
        convenience function for setting the flowrate

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
        # await self.inert_flow_controller.set_flow_rate(self.flowrate)
        # await self.dilutant_flow_contrller.set_flow_rate(self.flowrate*(1-self.odor_concentration))
        # await self.odor_flow_contrller.set_flow_rate(self.flowrate * self.odor_concentration)

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
            assert not any([v for k,v in self.odor_valve_states.items() if k not in odors]), "at least 1 odor valve is already open, if this is ok instead set 'odors_presen_ok' to True when calling this function"

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

    def toggle_odor_valve(self, odor, open_valve:bool = True):
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
            if not self.outlet_valve.is_open:
                assert any([v for k,v in self.odor_valve_states.items() if k!=odor]), "no alternative air paths, cannot close outlet valve"
            self.odor_valves[odor].close()

    def toggle_outlet_valve(self, open_valve = True):
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
            assert any(list(self.odor_valve_states.values())), "no alternative air paths, cannot close outlet valve"
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