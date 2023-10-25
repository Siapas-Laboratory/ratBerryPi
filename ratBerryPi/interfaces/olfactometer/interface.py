from ratBerryPi.interfaces.base import BaseInterface
from pathlib import Path
import RPi.GPIO as GPIO
from ratBerryPi.resources import Valve
import yaml
import alicat
import asyncio
import time

class Olfactometer(BaseInterface):
    def __init__(self, on, config_file = Path(__file__).parent/"config.yaml"):
        super(Olfactometer, self).__init__(on)
        with open(config_file, 'r') as f:
            self.config = yaml.safe_load(f)

        self.odor_valves = {k: Valve(k, self, v) for k,v in self.config["odor_valves"].items()}
        self.outlet_valve = Valve("outlet_valve", self, self.config["outlet_valve"], NC = False)
        self.release_valve = Valve("release_valve", self, self.config["release_valve"])
        
        # self.odor_flow_contrller = alicat.FlowController(self.config["odor_flow_controller"])
        # self.dilutant_flow_contrller = alicat.FlowController(self.config["dilutant_flow_controller"])
        # self.inert_flow_controller = alicat.FlowController(self.config["inert_flow_controller"])

        self.odor_concentration= self.config["initial_odor_concentration"]
        self.flowrate = self.config["initial_flowrate"]
        # self.logger = 

    @property
    def flowrate(self) -> float:
        return self._flowrate
    
    @flowrate.setter
    def flowrate(self, flowrate) -> None:
        self._flowrate = flowrate
        asyncio.run(self._set_controller_flowrates())

    @property
    def odor_concentration(self) -> float:
        return self._odor_concentration
    
    @odor_concentration.setter
    def odor_concentration(self, odor_concentration) -> None:
        self._odor_concentration = odor_concentration
        if hasattr(self, '_flowrate'):

            asyncio.run(self._set_controller_flowrates())

    def set_odor_concentration(self, odor_concentration:float) -> None:
        """
        convenience function for setting the odor concentration

        Args:
        -----
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
        -----
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

    def prep_odors(self, odors, wait_time:float = 1, odors_present_ok = False) -> None:
        """
        open the appropriate valves to allow the odor to flow to
        the mixing manifold

        Args:
        -----
        odors: list
            list of odors to prep
        wait_time: float
            time in seconds to wait after opening odor valves
            before closing the outlet valve
        """
        assert len(odors)>0, "no odors specified"
        if not odors_present_ok:
            assert not any([self.odor_valves[v].is_open for v in self.odor_valves if v not in odors])
        for odor in odors: 
            self.toggle_odor_valve(odor, open_valve = True)
        time.sleep(wait_time)
        self.toggle_outlet_valve(open_valve=False)

    def clear_mixing_manifold(self, wait_time:float = 1) -> None:
        """
        clear the mixing manifold of any odors

        Args:
        -----
        wait_time: float
            time in seconds to wait after opening the outlet valve
            before closing the odor valves
        """
        self.toggle_outlet_valve(open_valve=True)
        time.sleep(wait_time)
        for odor in self.odor_valves:
            self.toggle_odor_valve(odor, open_valve = False)

    def toggle_odor_valve(self, odor, open_valve = True):
        """
        convenience function for toggling odor valves with some input
        checking to avoid pressure buildup in the system

        Args:
        -----
        odor: str
            odor whose corresponding valve should be toggled
        open_valve: bool
            whether to open the valve
        """
        if open_valve:
            self.odor_valves[odor].open()
        else:
            if not self.outlet_valve.is_open:
                assert any([self.odor_valves[v].is_open for v in self.odor_valves if v!=odor]), "DANGER cannot close this valve because there are no other open valves"
            self.odor_valves[odor].close()

    def toggle_outlet_valve(self, open_valve = True):
        """
        convenience function for toggling the outlet valve with some input
        checking to avoid pressure buildup in the system

        Args:
        -----
        open_valve: bool
            whether to open the valve
        """
        if open_valve:
            self.outlet_valve.open()
        else:
            assert any([v.is_open for v in self.odor_valves.values()]), "no alternative air paths, cannot close outlet valve"
            self.outlet_valve.close()


    def release_odor(self) -> None:
        """
        switch the final valve to allow odor flow to
        the mask and inert air to flow to the exhaust
        """
        self.release_valve.open()

    def switch_to_exhaust(self) -> None:
        """
        switch the final valve to direct odor flow to
        the exhaust and inert air flow to the mask
        """
        self.release_valve.close()