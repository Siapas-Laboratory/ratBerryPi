from ratBerryPi.resources import Pump, Lickometer, LED, Valve
from ratBerryPi.resources.pump import Direction
from ratBerryPi.interfaces.reward.modules.base import BaseRewardModule
import typing
import time


class DefaultModule(BaseRewardModule):
    """
    class defining the default reward delivery module
    this module is equipped with a lickometer, speaker, led
    and optionally a valve
    """

    def load_from_config(self, config):
        self.lickometer =  Lickometer(f"{self.name}-lickometer", self.parent, config['lickPin'])
        self.speaker = self.parent.audio_interface.add_speaker(f"{self.name}-speaker", config["SDPin"])
        self.LED = LED(f"{self.name}-LED", self.parent, config["LEDPin"])