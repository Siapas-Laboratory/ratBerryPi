from pump import Syringe, Pump, PumpThread, EndTrackError
from plugins.lickometer import Lickometer
from plugins.audio import AudioInterface, Speaker
from plugins.led import LED
from plugins.valve import Valve
import RPi.GPIO as GPIO
import yaml
from datetime import datetime
import pandas as pd
import os
import threading
import time
import logging
from pathlib import Path
import math

class RewardModule:

    def __init__(self, name, pump, valve = None, dead_volume = 1):
        self.name = name
        self.pump = pump
        self.valve = valve
        self.pump_thread = None
        self.dead_volume = dead_volume

    def trigger_reward(self, amount, force = False, lick_triggered = False, sync = False, post_delay = 2):
        
        if force and self.pump_thread: 
            if self.pump_thread.running:
                self.pump_thread.stop()

        if sync:
            if lick_triggered:
                raise ValueError("cannot deliver lick-triggered reward synchronously")
            else:
                if self.valve: 
                    self.valve.open()
                self.pump.enable()
                self.pump.reserve(force = force)
                self.pump.move(amount, force = force, forward = True, pre_reserved = True, unreserve = False)
                if self.valve:
                    time.sleep(post_delay)
                    self.valve.close()
                self.pump.unreserve()
        else:
            self.pump_thread = PumpThread(self.pump, amount, lick_triggered, 
                                            valve = self.valve, forward = True, 
                                            parent = self, force = force, post_delay = post_delay)
            self.pump_thread.start()

    def fill_line(self, amount = None, pre_reserved = False, unreserve = False, refill = True):
        if amount is None:
            amount = self.dead_volume
        self.pump.enable()
        while amount>0:
            if self.valve: self.valve.close()
            if refill and hasattr(self.pump, 'fillValve'):
                self.pump.fillValve.open()
                self.pump.ret_to_max(pre_reserved = pre_reserved, unreserve = unreserve)
                self.pump.fillValve.close()
            if not self.pump.is_available(amount):
                avail = math.pi * ((self.syringe.ID/2)**2) * self.position
                if not hasattr(self.pump, 'fillValve'):
                    raise ValueError("the requested amount is greater than the volume left in the syringe and no fill valve has been specified to refill intermittently ")
            else:
                avail = amount
            if self.valve:
                self.valve.open()
            self.pump.move(avail, forward = True, pre_reserved = pre_reserved, unreserve = unreserve)
            if self.valve:
                self.valve.close()
            amount = amount - avail
        if self.valve: self.valve.close()

    def __del__(self):
        GPIO.cleanup()


class DefaultModule(RewardModule):

    def __init__(self, name, pump, lickometer, speaker, led, valve = None, dead_volume = 1, reward_thresh = 3):

        super().__init__(name, pump, valve, dead_volume)
        self.reward_thresh = reward_thresh
        self.pump_thread = None
        if lickometer: 
            self.lickometer =  lickometer
        if speaker: 
            self.speaker = speaker
        if led: 
            self.LED = led

    @property
    def pump_trigger(self):
        if hasattr(self, 'lickometer'):
            return self.lickometer.in_burst and (self.lickometer.burst_lick>self.reward_thresh)
        else:
            return None