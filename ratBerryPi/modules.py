from ratBerryPi.pump import Syringe, Pump, PumpThread, EndTrackError
from ratBerryPi.plugins.lickometer import Lickometer
from ratBerryPi.plugins.audio import AudioInterface, Speaker
from ratBerryPi.plugins.led import LED
from ratBerryPi.plugins.valve import Valve

import RPi.GPIO as GPIO
import time
import logging
import math

class RewardModule:
    """
    a base class for all reward modules
    any class defining a reward module should inherit from this class
    """
    def __init__(self, name, pump:Pump, valve:Valve, dead_volume:float = 1):
        self.name = name
        self.pump = pump
        self.valve = valve
        # TODO: reward_thread shouldn't be a module level property
        # there should be a pump_thread property that belongs to the pump
        self.reward_thread = None
        self.dead_volume = dead_volume

    @property
    def pump_trigger(self):
        raise NotImplementedError("The pump_trigger property must be specified for lick triggered reward delivery")

    def trigger_reward(self, amount:float, force:bool = False, triggered = False, sync = False, post_delay = 1):
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
        post_delay: float
            amount of time in seconds to wait after reward delivery to ensure the entire reward amount
            is has been delivered. setting this value too small will result in less reward being delievered
            than requested
        """
        
        if force and self.reward_thread: 
            # if forcing stop any running reward delivery threads
            if self.reward_thread.running:
                self.reward_thread.stop()

        if sync:
            if triggered:
                raise ValueError("cannot deliver lick-triggered reward synchronously")
            else:   
                self.valve.open() # if make sure the valve is open before delivering reward
                self.pump.reserve(force = force)
                # make sure the fill valve is closed if the pump has one
                if hasattr(self.pump, 'fillValve'):
                    self.pump.fillValve.close()
                # deliver the reward
                self.pump.move(amount, force = force, direction = 'forward', 
                               pre_reserved = True, unreserve = False)
                # wait then close the valve
                time.sleep(post_delay)
                self.valve.close()
                self.pump.unreserve()
        else: # spawn a thread to deliver reward asynchronously
            self.reward_thread = PumpThread(self.pump, amount, triggered, close_fill = True,
                                            valve = self.valve, direction = 'forward', 
                                            trigger_source = self, force = force, post_delay = post_delay)
            self.reward_thread.start()

    def fill_line(self, amount:float = None, pre_reserved:bool = False, unreserve:bool = False, refill:bool = True):
        if amount is None: amount = self.dead_volume
        while amount>0:
            if self.valve: self.valve.close()
            if refill and hasattr(self.pump, 'fillValve'):
                if not self.pump.at_max_pos:
                    self.pump.fillValve.open()
                    self.pump.ret_to_max(pre_reserved = pre_reserved, unreserve = unreserve)
                    self.pump.fillValve.close()
            if not self.pump.is_available(amount):
                avail = self.pump.vol_left - .1
                if not hasattr(self.pump, 'fillValve'):
                    raise ValueError("the requested amount is greater than the volume left in the syringe and no fill valve has been specified to refill intermittently ")
            else:
                avail = amount
            if self.valve:
                self.valve.open()
            self.pump.move(avail, direction = 'forward', pre_reserved = pre_reserved, unreserve = unreserve)
            if self.valve:
                self.valve.close()
            amount = amount - avail
        if self.valve: self.valve.close()

    def __del__(self):
        GPIO.cleanup()


class DefaultModule(RewardModule):
    """
    class defining the default reward delivery module
    this module is equipped with a lickometer, speaker, led
    and optionally a valve
    """

    def __init__(self, name, pump, lickometer:Lickometer, speaker:Speaker, led:LED,
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