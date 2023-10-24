from ratBerryPi.interfaces.base_interface import BaseInterface
from ratBerryPi.resources import Syringe, Pump, Lickometer, AudioInterface, Speaker, LED, Valve, ResourceLocked
from ratBerryPi.interfaces.reward.modules import *

import RPi.GPIO as GPIO
import yaml
from datetime import datetime
import pandas as pd
import os
import threading
import time
import logging
from pathlib import Path

ETHERNET = {
    "port0": {
        "LEDPin": "GPA0",
        "lickPin": 9,
        "SDPin": 10,
        "valvePin": "GPA1"},
    "port1": {
        "LEDPin": "GPA2",
        "lickPin": 11,
        "SDPin": 12,
        "valvePin": "GPA3"},
    "port2": {
        "LEDPin": "GPA4",
        "lickPin": 13,
        "SDPin": 14,
        "valvePin": "GPA5"},
    "port3": {
        "LEDPin": "GPA6",
        "lickPin": 15,
        "SDPin": 16,
        "valvePin": "GPA7"},
    "port4": {
        "LEDPin": "GPB0",
        "lickPin": 17,
        "SDPin": 18,
        "valvePin": "GPB1"},
    "port5": {
        "LEDPin": "GPB2",
        "lickPin": 19,
        "SDPin": 20,
        "valvePin": "GPB3"},
    "port6": {
        "LEDPin": "GPB4",
        "lickPin": 21,
        "SDPin": 22,
        "valvePin": "GPB5"},
    "port7": {
        "LEDPin": "GPB6",
        "lickPin": 23,
        "SDPin": 24,
        "valvePin": "GPB7"}
}

class NoSpeaker(Exception):
    pass

class NoLED(Exception):
    pass

class NoLickometer(Exception):
    pass

class NoFillValve(Exception):
    pass

class RewardInterface(BaseInterface):
    """
    An interface for controlling the reward module

    ...

    Methods
    -------

    calibrate(pump)
    fill_lines(amounts)
    record(reset = True)
    save()
    trigger_reward(module, amount, force = False, triggered = False)
    toggle_auto_fill(on)
    change_syringe(syringeType, all = False, module = None, pump=None)
    reset_licks(module = None, lickometer = None)
    reset_all_licks()
    toggle_LED(on, module = None, led = None)
    play_tone(freq, dur, volume = 1, module = None, speaker = None)

    """

    def __init__(self, config_file = Path(__file__).parent/"default_config.yaml", load_defaults:bool = True, on:threading.Event = None):
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
            load_defaults: bool
                flag to automatically load all default modules
        
        """

        self.on = threading.Event() if not on else on
        if not on.is_set():
            self.on.set()
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
            self.config['pumps'][i]['modePins'] = tuple(self.config['pumps'][i]['modePins'])
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
        self.recording = False
        self.log = []
        
        if load_defaults:
            # TODO: it could be worth coming up with a more general framework for loading modules
            # perhaps define an abstract method in the base RewardModule class that must be overwritten
            # with a function for the module to load itself from entries in the config file
            self.load_default_modules()

        self.auto_fill = False
        self.auto_fill_thread = threading.Thread(target = self._fill_syringes)
        self.auto_fill_thread.start()

    def load_default_modules(self):

        for i in self.config['modules']:
            if self.config['modules'][i]['type'] == 'default':
                pump = self.pumps[self.config['modules'][i]['pump']]
                dead_volume = self.config['modules'][i].get('dead_volume', 1)
                if 'port' in self.config['modules'][i]:
                    port = self.config['modules'][i]['port']
                    port_pins =  ETHERNET[port]
                else:
                    for j in ['valvePin', 'SDPin', 'lickPin', 'LEDPin']:
                        port_pins[j] = self.config['modules'][i].get(j)
                args = {'pump': pump, 'dead_volume': dead_volume}

                if port_pins['valvePin']: 
                    args['valve'] = Valve(f"{i}-valve", self, port_pins['valvePin'])
                if port_pins['LEDPin']:
                    args['led'] = LED(f"{i}-LED", self, port_pins["LEDPin"])
                if port_pins['lickPin']:
                    args['lickometer'] = Lickometer(f"{i}-lickometer", self, port_pins["lickPin"], self.on)
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

    def fill_lines(self, modules, prime_amount = 1, res_amount = None, blocking = False, timeout = 1):
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
        
        # TODO: this portion needs to be tested
        # # check if there is enough fluid in the syringes to prime the lines
        # for p in pumps:
        #     amt = res_amounts[p]
        #     for m,v in prime_amounts.items():
        #         if m.pump == p:
        #             amt += v
        #     if not p.is_available(amt):
        #         raise Exception("Not enough fluid to prime the lines")

        # make sure all valves are closed before starting

        lock_statuses = []
        for m in self.modules:
            if hasattr(m, 'valve'):
                acquired = m.valve.lock.acquire(blocking, timeout)
                lock_statuses.append(acquired)
                m.valve.close()

        # reserve all pumps
        for p in pumps: 
            acquired = p.lock.acquire(blocking, timeout)
            lock_statuses.append(acquired)
            if hasattr(p, 'fillValve'):
                p.fillValve.lock.acquire(blocking, timeout)      

        if all(lock_statuses):
            # prime all reservoirs
            for p, amt in res_amounts.items():
                logging.info(f"priming reservoir for {p.name}")
                if hasattr(p, 'fillValve'):
                    p.fillValve.open()
                p.move(amt, direction = 'forward')
                if hasattr(p, 'fillValve'):
                    p.fillValve.close()

            # prime all lines
            for m, amt in prime_amounts.items():
                logging.info(f'priming line for {m.name}')
                m.fill_line(amt, refill = False)
            
            # refill the syringes
            for p in pumps:
                logging.info(f'refilling syringe on {p.name} with the amount used to prime the lines')
                if hasattr(p, 'fillValve'):
                    p.fillValve.open()
                    p.ret_to_max()
                    p.fillValve.close()
                    time.sleep(.1)

            # fill the lines for all modules
            for m in modules:
                logging.info(f'filling line for {m.name}')
                m.fill_line()

            # refill the syringes
            for p in pumps:
                logging.info(f'refilling syringe on {p.name}')
                if hasattr(p, 'fillValve'):
                    p.fillValve.open()
                    p.ret_to_max()
                    p.fillValve.close()
                    time.sleep(.1)
                p.lock.release()

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

        #TODO: should consider  using python's logging library directly for all logging
        # currently the only real reason why plugins take as an argument their parent class
        # is so we can access a common log list from the reward interface object but with 
        # the logging module this would  not be necessary

        df = pd.DataFrame(self.log)
        df = df.sort_values('time')
        fname = datetime.strftime(datetime.now(), "%Y_%m_%d_%H_%M_%S.csv")
        data_dir = os.path.join(os.path.expanduser('~'), ".ratBerryPi", "data")
        os.makedirs(data_dir, exist_ok = True)
        df.to_csv(os.path.join(data_dir,fname)) 
        logging.info('saved!')
        self.recording = False

    def trigger_reward(self, module, amount:float, force:bool = False, triggered:bool = False, sync:bool = False, post_delay:float = 2):
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
            triggered: bool
                whether or not to deliver the reward in a lick-triggered manner.
            sync: bool
                flag to deliver reward synchronously. if set to true this function is blocking
                NOTE: triggered reward delivery is not supported when delivering reward synchronously
            post_delay: float
                amount of time in seconds to wait after reward delivery to ensure the entire reward amount
                is has been delivered. setting this value too small will result in less reward being delievered
                than requested

        """

        self.modules[module].trigger_reward(amount, force = force, triggered = triggered, 
                                            sync = sync, post_delay = post_delay)

    def _fill_syringes(self):
        """
        Asynchronously fill all syringes whenever the pumps 
        are not in use. This method is not meant to be called
        directly. Use toggle_auto_fill to turn on auto-filling
        """

        while self.on.is_set():
            if self.auto_fill:
                for i in self.pumps:
                    if not self.pumps[i].at_max_pos:
                        if not self.pumps[i].enabled: 
                            self.pumps[i].enable()
                        try:
                            # it takes long to check that all the valves are closed except the fill valve
                            # maybe just assume they are closed ( as they should be)
                            # for m in self.modules.values():
                            #     if m.pump == self.pumps[i]:
                            #         if m.valve: m.valve.close()
                            if hasattr(self.pumps[i], 'fillValve'):
                                self.pumps[i].fillValve.open()
                            else:
                                logging.warning(f"{i} has no specified fill valve")
                            self.pumps[i].single_step(direction = 'backward')
                        except ResourceLocked:
                            pass
                    elif hasattr(self.pumps[i], 'fillValve'):
                        self.pumps[i].fillValve.close()
            # this sleep is necessasry to avoid interfering
            # with other tasks that may want to use the pump
            time.sleep(.0005)

    def toggle_auto_fill(self, on:bool):
        """
        turn auto-filling of the syringes on or off

        Args:
            on: bool
                whether or not to turn auto-filling on
        """
        if not on:
            for i in self.pumps:
                if hasattr(self.pumps[i], 'fillValve'):
                    try:
                        self.pumps[i].fillValve.close()
                    except ResourceLocked:
                        pass
        self.auto_fill = on

    def change_syringe(self, syringeType:str, all:bool = False, module:str = None, pump:str=None):
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
    
    def reset_licks(self, module:str = None, lickometer:str = None):
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
    
    def toggle_LED(self, on:bool, module:str = None, led:str = None):
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

    def play_tone(self, freq:float, dur:float, volume:float = 1, module:str = None, speaker:str = None):
        """
        play a sine tone from a specified speaker or the speaker on the specified module

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
            speaker: str
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

    def toggle_valve(self, module:str, open_valve:bool):
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

    def stop(self):
        if self.on.is_set(): self.on.clear()
        self.auto_fill_thread.join()
        GPIO.cleanup()