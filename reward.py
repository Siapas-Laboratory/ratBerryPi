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
    """
    An interface for controlling the reward module

    ...

    Methods
    -------

    calibrate(pump)
    fill_lines(amounts)
    record(reset = True)
    save()
    trigger_reward(module, amount, force = False, lick_triggered = False)
    toggle_auto_fill(on)
    change_syringe(syringeType, all = False, module = None, pump=None)
    reset_licks(module = None, lickometer = None)
    reset_all_licks()
    toggle_LED(on, module = None, led = None)
    play_tone(freq, dur, volume = 1, module = None, speaker = None)

    """

    def __init__(self, burst_thresh = .5, reward_thresh = 1):
        """
        Constructs the reward interface from the config file

        Args:
            burst_thresh: float
                a threshold to be set on the inter-lick intervals
                for detecting lick bursts. this should be specified
                in units of seconds.
            reward_thresh: int
                the number of licks within a lick burst before the animal
                starts receiving reward when using the lick-triggered reward mode
        
        """

        GPIO.setmode(GPIO.BCM)
        with open(Path(__file__).parent/'config.yaml', 'r') as f:
            config = yaml.safe_load(f)

        self.pumps = {}
        for i in config['pumps']: 

            syringeType = config['pumps'][i].pop('syringeType') if 'defaultSyringeType' in config['pumps'][i] else None
            syringe = Syringe(syringeType)
            config['pumps'][i]['syringe'] = syringe
            
            if 'GPIOPins' not in config['pumps'][i]:
                raise ValueError(f"Missing argument 'GPIOPins' for pump '{i}'")
            elif len(config['pumps'][i]['GPIOPins'])!=3:
                raise ValueError(f"Expected 3 pins to be specified for argument 'GPIOPins' for pump '{i}', {len(config['pumps'][i]['GPIOPins'])} provided")
            
            config['pumps'][i]['GPIOPins'] = tuple(config['pumps'][i]['GPIOPins'])
            self.pumps[i] = Pump(**config['pumps'][i])

        self.plugins = {}
        self.audio_interface = AudioInterface()

        if 'plugins' in config:
            for k, v in config['plugins'].items():
                if v['type'] == 'lickometer':
                    self.plugins[k] = Lickometer(k, v['lickPin'], burst_thresh = burst_thresh, parent = self)
                if v['type'] == 'LED':
                    self.plugins[k] = LED(k, v['LEDPin'])
                elif v['type'] == 'speaker':
                    self.plugins[k] = Speaker(k, self.audio_interface, v['SDPin'])

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
        """
        Set the position of a provided pump to 0

        Args:
            pump: str
                name of the pump to calibrate
        """
        self.pumps[pump].calibrate()

    def fill_lines(self, amounts):
        """
        fill the lines leading up to the specified reward ports
        with fluid

        Args:
            amounts: dict
                a dictionary specifying the amount of fluid to 
                fill the line leading up to each module with. keys
                should be modules and values should be amounts in mL
        """

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
        """
        start a log of all events that occur on the interface,
        including any lick events or cue triggers

        Args:
            reset: bool
                whether or not to reset the lick counts on all
                lickometers before recording
        """
        self.recording = True
        if reset:
            self.reset_all_licks()
        for i in self.modules:
            self.modules[i].log = []
            self.modules[i].recording = True
        self.log = [{'time': datetime.now(), 'event': 'start', 'module': None}]
        logging.info('started recording')

    def save(self):
        """
        save the logs
        """

        df = pd.DataFrame(self.log)
        df = df.sort_values('time')
        fname = datetime.strftime(datetime.now(), "%Y_%m_%d_%H_%M_%S.csv")
        df.to_csv(os.path.join('data',fname)) 
        logging.info('saved!')
        self.recording = False

    def trigger_reward(self, module, amount, force = False, lick_triggered = False):
        """
        trigger reward delivery on a provided reward module

        Args:
            module: str
                name of the module to trigger reward delivery on
            amount: float
                amount of reward in mL to be delivered at the reward port
            force: bool
                whether or not to force reward delivery even if the pump is in use.
                Note, this will not force reward delivery if the pump carriage sled
                is at the end of the track
            lick_triggered: bool
                whether or not to deliver the reward in a lick-triggered manner. 
        """
        self.modules[module].trigger_reward(amount, force = force, lick_triggered = lick_triggered)
        for i in self.pumps:
            if hasattr(self.pumps[i], 'fillValve'):
                self.pumps[i].fillValve.close()

    def _fill_syringes(self):
        """
        Asynchronously fill all syringes whenever the pumps 
        are not in use. This method is not meant to be called
        directly. Use toggle_auto_fill to turn on auto-filling
        """

        while True:
            for i in self.pumps:
                if (not self.pumps[i].in_use) and self.auto_fill:
                    if not self.pumps[i].at_max_pos:
                        if not self.pumps[i].enabled:
                            self.pumps[i].enable()
                            if hasattr(self.pumps[i], 'fillValve'):
                                self.pumps[i].fillValve.open()
                            else:
                                logging.warning(f"{i} has no specified fill valve")
                            self.pumps[i].single_step(False, "Full")
                    else:
                        if hasattr(self.pumps[i], 'fillValve'):
                            self.pumps[i].fillValve.close()
            # this sleep is necessasry to avoid interfering
            # with other tasks that may want to use the pump
            time.sleep(.0005)

    def toggle_auto_fill(self, on):
        """
        turn auto-filling of the syringes on or off

        Args:
            on: bool
                whether or not to turn auto-filling on
        """
        if not on:
            for i in self.pumps:
                if hasattr(self.pumps[i], 'fillValve'):
                    self.pumps[i].fillValve.close()
        self.auto_fill = on

    def change_syringe(self, syringeType, all = False, module = None, pump=None):
        """
        change the syringe type either on all pumps or one pump specified by either
        it's name or a module that it is attached to

        Args:
            syringeType: str
                name of the syringe type to switch to. options include: 
                'BD1mL', 'BD5mL', 'BD10mL', 'BD30mL', 'BD50/60mL'. These
                options are keys to the dirctionary syringeTypeDict defined
                in the Syringe class in pump.py. To add more syringes add
                a field to this dictionary with the ID of the syringe and 
                the maximum length the syringe can be withdrawn to in cm.
            all: bool
                whether or not to change the syringe type for all pumps
            module: str
                the name of the module with the pump whose syringe is to be changed
            pump: str
                the name of the pump whose syringe is to be changed

        """
        if all: 
            for i in self.pumps:
                self.pumps[i].change_syringe(syringeType=syringeType)
        elif pump:
            self.pumps[pump].change_syringe(syringeType)
        elif module: 
            self.modules[module].pump.change_syringe(syringeType)
    
    def reset_licks(self, module = None, lickometer = None):
        """
        reset licks to 0 on a given module's lickometer
        or a specified lickometer

        Args:
            module: str
                name of the module to reset licks on
            lickometer: str
                name of the lickometer to reset licks on
        """
        if module is not None:
            if hasattr(self.modules[module], 'lickometer'):
                self.modules[module].lickometer.reset_licks()
            else:
                raise NoLickometer
        elif lickometer is not None:
            if lickometer in self.plugins:
                self.plugins[lickometer].reset_licks()
            else:
                raise NoLickometer
        
    def reset_all_licks(self):
        """
        reset licks to 0 on all lickometers
        """
        for i in self.plugins:
            if isinstance(self.plugins[i], Lickometer):
                self.plugins[i].reset_licks()
    
    def toggle_LED(self, on, module = None, led = None):
        """
        toggle a given LED on or off

        Args:
            on: bool
                whether to turn the LED on (True) or off (False)
            module: str
                name of the module whose LED should be toggled
            led: str
                name of the LED to be toggled
        """

        if module is not None:
            if hasattr(self.modules[module], 'LED'):
                if isinstance(self.modules[module].LED, LED):
                    if on: self.modules[module].LED.turn_on()
                    else: self.modules[module].LED.turn_off()
                else:
                    raise NoLED
            else:
                raise NoLED
        elif led is not None:
            if isinstance(self.plugins[led], LED):
                if on: self.plugins[led].turn_on()
                else: self.plugins[led].turn_off()
            else:
                raise NoLED

    def play_tone(self, freq, dur, volume = 1, module = None, speaker = None):
        """
        play a sine tone from a given speaker

        Args:
            freq: float
                frequency of the sine tone to be played in Hz
            dur: float
                duration of the tone to be played in seconds
            volume: float
                fraction of max volume to play the tone at;
                should be a value from 0 to 1
            module: str
                the name of the module whose speaker the tone should be played from
            speaker
                the name of the speaker the tone should be played from
        """
        if module is not None:
            if hasattr(self.modules[module], 'speaker'):
                if isinstance(self.modules[module].speaker, Speaker):
                    self.modules[module].speaker.play_tone(freq, dur, volume)
                else:
                    raise NoSpeaker
            else:
                raise NoSpeaker
        elif speaker is not None:
            if isinstance(self.plugins[speaker], Speaker):
                self.plugins[speaker].play_tone(freq, dur, volume)
            else:
                raise NoSpeaker
    
    def __del__(self):
        GPIO.cleanup()


class RewardModule:

    def __init__(self, name, pump, valvePin= None, plugins = {}, reward_thresh = 3):

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
        if self.pump.at_min_pos: raise EndTrackError
        if force and self.pump_thread: self.pump_thread.stop()
        self.pump_thread = PumpThread(self.pump, amount, lick_triggered, 
                                      valve = self.valve, forward = True, 
                                      parent = self)
        self.pump_thread.start()

    def __del__(self):
        GPIO.cleanup()
