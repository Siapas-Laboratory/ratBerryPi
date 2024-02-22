from ratBerryPi.resources import Pump, Lickometer, LED, Valve
from ratBerryPi.resources.pump import PumpTrigger, TriggerMode, Direction
from ratBerryPi.interfaces.reward.modules.base import BaseRewardModule
import typing
import time


class ContinuousLickTrigger(PumpTrigger):
    @property
    def armed(self):
        return self.parent.lickometer.in_burst and (self.parent.lickometer.burst_lick>self.reward_thresh)
    
class ResetableLickTrigger(PumpTrigger):
    def __init__(self, parent):
        super(ResetableLickTrigger, self).__init__(parent)
        self.ref_lick_num = self.parent.lickometer.licks

    @property
    def armed(self):
        return (self.parent.lickometer.licks - self.ref_lick_num) >= self.parent.reward_thresh
    
    def reset(self):
        self.ref_lick_num = self.parent.lickometer.licks


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
    
    def trigger_reward(self, amount:float, force:bool = False, trigger_mode = TriggerMode.NO_TRIGGER, 
                       sync = False, post_delay = 1):
        """
        trigger reward delivery

        Args:
        -----
        amount: float
            the total amount of reward to be delivered in mLs
        force: bool
            flag to force reward delivery even if the pump is in use
        triggered: bool
            flag to deliver reward in triggered mode
        sync: bool
            flag to deliver reward synchronously. if set to true this function is blocking
            NOTE: triggered reward delivery is not supported when delivering reward synchronously
        """
        
        if force and self.pump.thread: 
            # if forcing stop any running reward delivery threads
            if self.pump.thread.running:
                self.pump.thread.stop()
        elif self.pump.thread:
            if self.pump.thread.running:
                raise ResourceLocked("Pump In Use")

        if sync:
            if trigger_mode == TriggerMode.CONTINUOUS_TRIGGER:
                raise ValueError("cannot deliver continuous lick-triggered reward synchronously")
            else:
                acquired = self.acquire_locks()
                if acquired:
                    if trigger_mode == TriggerMode.SINGLE_TRIGGER:
                        self.reset_lick_trigger.reset()

                    if self.pump.direction == Direction.BACKWARD and self.pump.hasFillValve:
                        self.valve.close()
                        self.fillValve.open()
                        self.pump.move(.05 * self.pump.mlPerCm, Direction.FORWARD)

                    if trigger_mode == TriggerMode.SINGLE_TRIGGER:
                        while not self.reset_lick_trigger.armed:
                            time.sleep(.001)

                    self.valve.open() # if make sure the valve is open before delivering reward
                    # make sure the fill valve is closed if the pump has one
                    if self.pump.hasFillValve: self.pump.fillValve.close()
                    # deliver the reward
                    self.pump.move(amount, force = force, direction = Direction.FORWARD)
                    # wait then close the valve
                    time.sleep(self.post_delay)
                    self.valve.close()
                    # release the locks
                    self.release_locks()

        else: # spawn a thread to deliver reward asynchronously
            print(trigger_mode)
            print(trigger_mode == TriggerMode.SINGLE_TRIGGER)
            trigger = self.reset_lick_trigger if trigger_mode == TriggerMode.SINGLE_TRIGGER else self.cont_lick_trigger
            self.pump.async_pump(amount, trigger_mode, close_fill = True, 
                                 valve = self.valve, direction = Direction.FORWARD,
                                 trigger = trigger, post_delay = self.post_delay)

    def load_from_config(self, config):
        self.lickometer =  Lickometer(f"{self.name}-lickometer", self.parent, config['lickPin'])
        self.speaker = self.parent.audio_interface.add_speaker(f"{self.name}-speaker", config["SDPin"])
        self.LED = LED(f"{self.name}-LED", self.parent, config["LEDPin"])
        self.cont_lick_trigger = ContinuousLickTrigger(self)
        self.reset_lick_trigger = ResetableLickTrigger(self)
