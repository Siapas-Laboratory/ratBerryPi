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

        self.valves = {k: Valve(k, self, v) for k,v in self.config["odor_valves"].items()}
        self.outlet_valve = Valve("outlet_valve", self, self.config["outlet_valve"], NC = False)
        self.release_valve = Valve("release_valve", self, self.config["release_valve"])
        
        self.odor_flow_contrller = alicat.FlowController(self.config["odor_flow_controller"])
        self.dilutant_flow_contrller = alicat.FlowController(self.config["dilutant_flow_controller"])
        self.inert_flow_controller = alicat.FlowController(self.config["inert_flow_controller"])

        self.dilution= self.config["initial_dilution"]
        self.flowrate = self.config["initial_flowrate"]
        # self.logger = 

    @property
    def flowrate(self):
        return self._flowrate
    
    @flowrate.setter
    def flowrate(self, flowrate):
        asyncio.run(self._set_flowrate(flowrate))

    @property
    def dilution(self):
        return self._dilution
    
    @dilution.setter
    def dilution(self, dilution):
        self._dilution = dilution
        if hasattr(self, '_flowrate'):
            asyncio.run(self._set_flowrate())

    def start(self):
        if not self.on.is_set(): self.on.set()

    def set_dilution(self, dilution:float):
        if not 0<=dilution<=1:
            raise ValueError("argument 'dilution' must be a value from 0-1")
        self.dilution = dilution

    def set_flowrate(self, flowrate):
        self.flowrate = flowrate

    async def _set_flowrate(self, flowrate = None):
        if not flowrate: flowrate = self.flowrate
        await self.inert_flow_controller.set_flow_rate(flowrate)
        await self.dilutant_flow_contrller.set_flow_rate(flowrate*(1-self.dilution))
        await self.odor_flow_contrller.set_flow_rate(flowrate * self.dilution)
        self._flowrate = flowrate

    def prep_odor(self, valve, wait_time = 1):
        self.valves[valve].open()
        time.sleep(wait_time)
        self.valves["null"].close()

    def release_odor(self):
        self.release_valve.open()

    def switch_to_exhaust(self):
        self.release_valve.close()

    def stop(self):
        GPIO.cleanup()