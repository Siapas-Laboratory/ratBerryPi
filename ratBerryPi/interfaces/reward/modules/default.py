from ratBerryPi.resources import Pump, Lickometer, Speaker, LED, Valve
from ratBerryPi.interfaces.reward.modules import BaseRewardModule


class DefaultModule(BaseRewardModule):
    """
    class defining the default reward delivery module
    this module is equipped with a lickometer, speaker, led
    and optionally a valve
    """

    def __init__(self, name, pump:Pump, lickometer:Lickometer, speaker:Speaker, led:LED,
                  valve:Valve, dead_volume:float = 1, reward_thresh:int = 3):
        
        """
        
        """

        super().__init__(name, pump, valve, dead_volume)
        self.reward_thresh = reward_thresh
        self.reward_thread = None
        self.lickometer =  lickometer
        self.speaker = speaker
        self.LED = led

    @property
    def pump_trigger(self):
        return self.lickometer.in_burst and (self.lickometer.burst_lick>self.reward_thresh)