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
from modules import *

with open(Path(__file__).parent/'ports.yaml', 'r') as f:
    PORTS = yaml.safe_load(f)

class NoSpeaker(Exception):
    pass

class NoLED(Exception):
    pass

class NoLickometer(Exception):
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

    def __init__(self, config_file, load_defaults = True):
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

        with open(config_file, 'r') as f:
            self.config = yaml.safe_load(f)

        self.pumps = {}
        # load all pumps
        for i in self.config['pumps']: 
            if 'syringeType' in self.config['pumps'][i]:
                syringe = Syringe(self.config['pumps'][i].pop('syringeType'))
            else:
                syringe = Syringe()
            self.config['pumps'][i]['syringe'] = syringe
            self.config['pumps'][i]['GPIOPins'] = tuple(self.config['pumps'][i]['GPIOPins'])
            self.pumps[i] = Pump(i, **self.config['pumps'][i])

        self.plugins = {}
        self.audio_interface = AudioInterface()

        # load any loose plugins not attached to a module
        if 'plugins' in self.config:
            for k, v in self.config['plugins'].items():
                v['parent'] = self
                plugin_type = v.pop('type')
                if plugin_type == 'Speaker':
                    v['audio_interface'] == self.audio_interface
                constructor = globals()[plugin_type]
                self.plugins[k] = constructor(k, **v)

        self.modules = {}
        if load_defaults:
            self.load_default_modules()

        self.recording = False
        self.log = []

        self.auto_fill = False
        self.auto_fill_thread = threading.Thread(target = self._fill_syringes)
        self.auto_fill_thread.start()

    def load_default_modules(self):

        for i in self.config['modules']:
            if self.config['modules'][i]['type'] == 'default':
                pump = self.pumps[self.config['modules'][i]['pump']]
                dead_volume = self.config['modules'][i].get('dead_volume')
                if 'port' in self.config['modules'][i]:
                    port = self.config['modules'][i]['port']
                    port_pins = PORTS[port]
                else:
                    for j in ['valvePin', 'SDPin', 'lickPin', 'LEDPin']:
                        port_pins[j] = self.config['modules'][i].get(j)
                args = {'pump': pump, 'dead_volume': dead_volume}

                if port_pins['valvePin']: 
                    args['valve'] = Valve(f"{i}-valve", self, port_pins['valvePin'])
                if port_pins['LEDPin']:
                    args['led'] = LED(f"{i}-LED", self, port_pins["LEDPin"])
                if port_pins['lickPin']:
                    args['lickometer'] = Lickometer(f"{i}-lickometer", self, port_pins["lickPin"])
                if port_pins['SDPin']:
                    args['speaker'] = Speaker(f"{i}-speaker", self, self.audio_interface, port_pins["SDPin"])
                
                self.modules[i] = DefaultModule(i, **args)
        

    def calibrate(self, pump):
        """
        Set the position of a provided pump to 0

        Args:
            pump: str
                name of the pump to calibrate
        """
        self.pumps[pump].calibrate()

    def fill_lines(self, modules, prime_amount = 1, res_amount = None):
        """
        fill the lines leading up to the specified reward ports
        with fluid

        Args:
            modules: list
                a list of all modules whose lines should be filled
            prime_amount: int, dict
                either a single value specifying the amount of fluid
                to fill all lines with or a dictionary specifying how
                much fluid to fill each line with. keys should be module
                names and values should be amounts in mL
            res_amount: int, dict
                either a single value specifying the amount of fluid
                to fill the lines leading up to all reservoirs with 
                or a dictionary specifying how much fluid to fill each line
                leading up to each reservoir. keys should be pump
                names and values should be amounts in mL

        """

        #TODO: clean up this function a bit
        #TODO: check availability ahead of time

        # temporarily turn off auto fill
        afill_was_on = self.auto_fill
        self.toggle_auto_fill(False)

        # get all unique pumps
        modules = list([self.modules[i] for i in modules])
        pumps = list(set([m.pump for m in modules]))

        if type(prime_amount) == int or float:
            prime_amounts = {i: prime_amount for i in modules}
        elif isinstance(prime_amount, dict):
            _modules = set([self.modules[i] for i in prime_amount])
            if not len(set(modules).intersection(_modules)) == len(modules):
                raise ValueError("the keys of 'prime_amount' should be the same as the specified modules")
            prime_amounts = prime_amount
        else:
            raise TypeError(f"invalid input of type {type(prime_amount)} for argument 'prime_amount'")

        if res_amount is None:
            res_amounts = {i: prime_amount for i in pumps}
        elif type(res_amount) == int or float:
            res_amounts = {i: res_amount for i in pumps}
        elif isinstance(res_amount, dict):
            _pumps = set([self.pumps[i] for i in res_amount])
            if not len(set(pumps).intersection(_pumps)) == len(pumps):
                raise ValueError("the keys of 'res_amount' should correspond to all pumps connected to the specified modules")
            res_amounts = res_amount
        else:
            raise TypeError(f"invalid input of type {type(res_amount)} for argument 'res_amount'")

        # make sure all valves are closed before starting
        for m in self.modules:
            if hasattr(m, 'valve'):
                m.valve.close()

        # reserve all pumps
        for p in pumps: p.reserve()
        
        # prime all reservoirs
        for p, amt in res_amounts.items():
            logging.info(f"priming reservoir for {p.name}")
            p.enable()
            if hasattr(p, 'fillValve'):
                p.fillValve.open()
            p.move(amt, True, pre_reserved = True, unreserve = False)
            if hasattr(p, 'fillValve'):
                p.fillValve.close()

        # prime all lines
        for m, amt in prime_amounts.items():
            logging.info(f'priming line for {m.name}')
            m.fill_line(amt, pre_reserved = True, unreserve = False)
        
        # refill the syringes with the amounts used to prime the lines
        for m, amt in prime_amounts.items():
            if hasattr(m.pump, 'fillValve'):
                m.pump.fillValve.open()
            logging.info(f'refilling syringe with the amount used to prime the line for {m.name}')
            m.pump.move(amt, False, pre_reserved = True, unreserve = False)
            if hasattr(m.pump, 'fillValve'):
                m.pump.fillValve.close()
                time.sleep(.1)

        for p, amt in res_amounts.items():
            logging.info(f'refilling syringe with the amount used to prime the reservoir for {p.name}')
            if hasattr(p, 'fillValve'):
                p.fillValve.open()
            p.move(amt, False, pre_reserved = True, unreserve = False)
            if hasattr(p, 'fillValve'):
                p.fillValve.close()

        # fill the lines for all modules
        for m in modules:
            logging.info(f'filling line for {m.name}')
            m.fill_line(pre_reserved = True, unreserve = False)
            if hasattr(m.pump, 'fillValve'):
                m.pump.fillValve.open()
            logging.info('reloading')
            m.pump.move(m.dead_volume, False, unreserve = False, pre_reserved = True)
            if hasattr(m.pump, 'fillValve'):
                m.pump.fillValve.close()

        for p in pumps: p.unreserve()
        self.toggle_auto_fill(afill_was_on) # turn autofill back on if it was on
        

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

    def trigger_reward(self, module, amount, force = False, lick_triggered = False, sync = False, post_delay = 2):
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

        self.modules[module].trigger_reward(amount, force = force, lick_triggered = lick_triggered, sync = sync, post_delay = post_delay)

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
        else:
            raise NoSpeaker

    def toggle_valve(self, module, open_valve):
        """
        toggle the valve for a given module open or close

        Args:
            module: str
                the name of the module with the valve to toggle
            open_valve: bool
                whether or not to open the valve
        """
        if hasattr(self.modules[module], "valve"):
            if open_valve:
                self.modules[module].valve.open()
            else:
                self.modules[module].valve.close()
    
    def __del__(self):
        GPIO.cleanup()
