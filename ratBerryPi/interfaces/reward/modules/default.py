from ratBerryPi.resources import Pump, Lickometer, LED, Valve
from ratBerryPi.interfaces.reward.modules.base import BaseRewardModule
import typing
import time


class DefaultModule(BaseRewardModule):
    """
    class defining the default reward delivery module
    this module is equipped with a lickometer, speaker, led
    and optionally a valve
    """

    def __init__(self, name, parent, pump:Pump, valvePin:typing.Union[int, str], dead_volume:float = 1, reward_thresh:int = 3):
        
        """
        
        """

        super().__init__(name, parent, pump, valvePin, dead_volume)
        self.reward_thresh = reward_thresh

    @property
    def pump_trigger(self):
        return self.lickometer.in_burst and (self.lickometer.burst_lick>self.reward_thresh)

    def load_from_config(self, config):
        self.lickometer =  Lickometer(f"{self.name}-lickometer", self.parent, config['lickPin'])
        self.speaker = self.parent.audio_interface.add_speaker(f"{self.name}-speaker", config["SDPin"])
        self.LED = LED(f"{self.name}-LED", self.parent, config["LEDPin"])