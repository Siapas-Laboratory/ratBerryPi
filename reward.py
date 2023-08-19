from pump import Syringe, Pump, PumpThread, EndTrackError
from plugins import lickometer, audio, led
from plugins.valve import Valve
import RPi.GPIO as GPIO
import yaml
from datetime import datetime
import pandas as pd
import os
import threading
import time
import logging

class NoSpeaker(Exception):
    pass

class NoLED(Exception):
    pass

class NoLickometer(Exception):
    pass

class PumpInUse(Exception):
    pass

class NoFillValve(Exception):
    pass

class RewardInterface:
    def __init__(self, burst_thresh = .5, reward_thresh = 1):

        GPIO.setmode(GPIO.BCM)
        with open('config.yaml', 'r') as f:
            config = yaml.safe_load(f)

        self.pumps = {}

        for i in config['pumps']: 
            syringeType = config['pumps'][i].pop('defaultSyringeType') if 'defaultSyringeType' in config['pumps'][i] else None
            ID = config['pumps'][i].pop('ID') if 'defaultID' in config['pumps'][i] else None
            syringe = Syringe(syringeType = syringeType, ID = ID)
            config['pumps'][i]['syringe'] = syringe
            
            if 'GPIOPins' not in config['pumps'][i]:
                raise ValueError(f"Missing argument 'GPIOPins' for pump '{i}'")
            elif len(config['pumps'][i]['GPIOPins'])!=3:
                raise ValueError(f"Expected 3 pins to be specified for argument 'GPIOPins' for pump '{i}', {len(config['pumps'][i]['GPIOPins'])} provided")
            
            config['pumps'][i]['GPIOPins'] = tuple(config['pumps'][i]['GPIOPins'])
            self.pumps[i] = Pump(**config['pumps'][i])

        self.plugins = {}
        self.audio_interface = audio.AudioInterface()

        if 'plugins' in config:
            for k, v in config['plugins'].items():
                if v['type'] == 'lickometer':
                    self.plugins[k] = lickometer.Lickometer(k, v['lickPin'], burst_thresh = burst_thresh, parent = self)
                if v['type'] == 'LED':
                    self.plugins[k] = led.LED(k, v['LEDPin'])
                elif v['type'] == 'speaker':
                    self.plugins[k] = audio.Speaker(k, self.audio_interface, v['SDPin'])

        self.modules = {}
        for i in config['modules']:
            config['modules'][i]['pump'] = self.pumps[config['modules'][i]['pump']]
            if 'plugins' in config['modules'][i]:
                config['modules'][i]['plugins'] = {k: self.plugins[v] for k,v in config['modules'][i]['plugins'].items()}

            self.modules[i] = RewardModule(i, **config['modules'][i], burst_thresh = burst_thresh, reward_thresh=reward_thresh)
        
        self.recording = False
        self.log = []

        self.auto_fill = False
        self.auto_fill_thread = threading.Thread(target = self._fill_syringes)
        self.auto_fill_thread.start()

    def calibrate(self, pump):
        self.pumps[pump].calibrate()

    def fill_lines(self, amounts):
        for i in amounts:
            self.modules[i].pump.enable()
            if hasattr(self.modules[i], 'valve'):
                self.modules[i].valve.open()
            if hasattr(self.modules[i].pump, 'fillValve'):
                self.modules[i].pump.fillValve.close()
            logging.info(f'filling {i}')
            self.modules[i].pump.move(amounts[i], True, unreserve = False)
            if hasattr(self.modules[i], 'valve'):
                self.modules[i].valve.close()
            if hasattr(self.modules[i].pump, 'fillValve'):
                self.modules[i].pump.fillValve.open()
            logging.info('reloading')
            self.modules[i].pump.move(amounts[i], False, unreserve = False)
        if hasattr(self.modules[i].pump, 'fillValve'):
            self.modules[i].pump.fillValve.close()


    def record(self, reset = True):
        self.recording = True
        if reset:
            self.reset_all_licks()
        for i in self.modules:
            self.modules[i].log = []
            self.modules[i].recording = True
        self.log = [{'time': datetime.now(), 'event': 'start', 'module': None}]
        logging.info('started recording')

    def save(self):
        df = pd.DataFrame(self.log)
        df = df.sort_values('time')
        fname = datetime.strftime(datetime.now(), "%Y_%m_%d_%H_%M_%S.csv")
        df.to_csv(os.path.join('data',fname)) 
        logging.info('saved!')
        self.recording = False

    def trigger_reward(self, module, amount, force = False, lick_triggered = False):
        self.modules[module].trigger_reward(amount, force = force, lick_triggered = lick_triggered)
        for i in self.pumps:
            if hasattr(self.pumps[i], 'fillValve'):
                self.pumps[i].fillValve.close()

    def _fill_syringes(self):
        #TODO: right now if there's no specified fill valve for a pump
        # we still fill without any valve control. is this ok? or should 
        # we throw an error?

        while True:
            for i in self.pumps:
                if (not self.pumps[i].in_use) and self.auto_fill:
                    if not self.pumps[i].at_max_pos:
                        if not self.pumps[i].enabled:
                            self.pumps[i].enable()
                            if hasattr(self.pumps[i], 'fillValve'):
                                self.pumps[i].fillValve.open()
                            self.pumps[i].single_step(False, "Full")
                    else:
                        if hasattr(self.pumps[i], 'fillValve'):
                            self.pumps[i].fillValve.close()
            # this sleep is necessasry to avoid interfering
            # with other tasks that may want to use the pump
            time.sleep(.0005)

    def toggle_auto_fill(self, on):
        if not on:
            for i in self.pumps:
                if hasattr(self.pumps[i], 'fillValve'):
                    self.pumps[i].fillValve.close()
        self.auto_fill = on

    def change_syringe(self, pump=None, syringeType=None, ID=None):
        if pump:
            self.pumps[pump].change_syringe(syringeType=syringeType, ID=ID)
        else:
            for i in self.pumps:
                self.pumps[i].change_syringe(syringeType=syringeType, ID=ID)
    
    def reset_licks(self, module):
        if hasattr(self.modules[module], 'lickometer'):
            self.modules[module].lickometer.reset_licks()
        else:
            raise NoLickometer
        
    def reset_all_licks(self):
        for i in self.modules:
            if hasattr(self.modules[i], 'lickometer'):
                self.modules[i].lickometer.reset_licks()
            else:
                raise NoLickometer
    
    def toggle_LED(self, on, module = None, LED = None):
        if module is not None:
            if hasattr(self.modules[module], 'LED'):
                if isinstance(self.modules[module].LED, led.LED):
                    if on: self.modules[module].LED.turn_on()
                    else: self.modules[module].LED.turn_off()
                else:
                    raise NoLED
            else:
                raise NoLED
        elif LED is not None:
            if isinstance(self.plugins[LED], led.LED):
                if on: self.plugins[LED].turn_on()
                else: self.plugins[LED].turn_off()
            else:
                raise NoLED

    def play_tone(self, freq, dur, volume = 1, module = None, speaker = None):
        if module is not None:
            if hasattr(self.modules[module], 'speaker'):
                if isinstance(self.modules[module].speaker, audio.Speaker):
                    self.modules[module].speaker.play_tone(freq, dur, volume)
                else:
                    raise NoSpeaker
            else:
                raise NoSpeaker
        elif speaker is not None:
            if isinstance(self.plugins[speaker], audio.Speaker):
                self.plugins[speaker].play_tone(freq, dur, volume)
            else:
                raise NoSpeaker
    
    def __del__(self):
        GPIO.cleanup()


class RewardModule:

    def __init__(self, name, pump, valvePin= None, plugins = {}, 
                burst_thresh = .5, reward_thresh = 3):

        self.pump = pump
        self.name = name
        self.reward_thresh = reward_thresh
        self.pump_thread = None

        for i,v in plugins.items():
            setattr(self, i, v)

        if valvePin is not None:
            self.valve = Valve(valvePin)
    
    @property
    def pump_trigger(self):
        if hasattr(self, 'lickometer'):
            return self.lickometer.in_burst and (self.lickometer.burst_lick>self.reward_thresh)
        else:
            return None

    def trigger_reward(self, amount, force = False, lick_triggered = False):
        
        if self.pump.in_use and not force: raise PumpInUse
        if self.pump.at_min_pos and not force: raise EndTrackError
        if force and self.pump_thread: self.pump_thread.stop()
        self.pump_thread = PumpThread(self.pump, amount, lick_triggered, 
                                      valve = self.valve, forward = True, 
                                      parent = self)
        self.pump_thread.start()

    def __del__(self):
        GPIO.cleanup()
