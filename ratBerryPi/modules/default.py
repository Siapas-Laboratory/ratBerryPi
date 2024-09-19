from ratBerryPi.resources import Pump, Lickometer, LED, Valve
from ratBerryPi.resources.pump import Direction
from ratBerryPi.modules.base import BaseRewardModule
import typing
import time


class DefaultModule(BaseRewardModule):
    """
    class defining the default reward delivery module
    this module is equipped with a lickometer, speaker, led
    and optionally a valve
    """

    def load_from_config(self, config: dict):
        """
        setup the module given a config
        """
        
        if 'lickBusPin' in config:
            self.lickometer = self.parent._lick_busses[config['lickBusPin']].add_lickometer(f"{self.name}-lickometer", config['lickPin'])
        else:
            self.lickometer =  Lickometer(f"{self.name}-lickometer", self.parent, config['lickPin'])
        self.speaker = self.parent.audio_interface.add_speaker(f"{self.name}-speaker", config["SDPin"])
        self.LED = LED(f"{self.name}-LED", self.parent, config["LEDPin"])