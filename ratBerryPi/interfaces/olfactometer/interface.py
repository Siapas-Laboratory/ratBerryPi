from ratBerryPi.interfaces.base import BaseInterface
from pathlib import Path
import RPi.GPIO as GPIO
from ratBerryPi.resources import Valve
import yaml

class Olfactometer(BaseInterface):
    def __init__(self, on, config_file = Path(__file__).parent/"config.yaml"):
        super(Olfactometer, self).__init__(self, on)
        with open(config_file, 'r') as f:
            self.config = yaml.safe_load(f)

        self.valves = {k: Valve(k, self, v) for k,v in self.config["manifold_valves"].items()}
        self.release_valve = Valve("release_valve", self, self.config["release_valve"])

        #TODO: need a plugin for the flow controllers
    
    @property
    def flowrate(self):
        return self._flowrate
    
    @flowrate.setter
    def flowrate(self, flowrate):
        #TODO: use flow controller plugin to set the flowrate on all controllers appropriately
        self._flowrate = flowrate

    @property
    def dilution(self):
        return self._dilution
    
    @dilution.setter
    def dilution_factor(self, dilution):
        #update flow rates
        self._dilution_factor = dilution

    def start(self):
        self._dilution_factor = self.config["initial_dilution"]
        self.set_flowrate(self.config["initial_flowrate"]) 
        if not self.on.is_set(): self.on.set()

    def set_dilution(self, dilution:float):
        if not 0<=dilution<=1:
            raise ValueError("argument 'dilution' must be a value from 0-1")
        self.dilution = dilution

    def set_flowrate(self, flowrate):
        self.flowrate = flowrate

    def prep_odor(self, valve):
        self.valves[valve].open()

    def release_odor(self):
        self.release_valve.open()
    
    def switch_to_exhaust(self):
        self.release_valve.close()

    def stop(self):
        GPIO.cleanup()