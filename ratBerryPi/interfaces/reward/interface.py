from ..base import BaseInterface
from ..audio.interface import AudioInterface
from ratBerryPi.resources import Pump, Lickometer, LED, Valve, ResourceLocked
from ratBerryPi.resources.pump import Syringe, Direction, EndTrackError, TriggerMode
from ratBerryPi.interfaces.reward.modules import *

import RPi.GPIO as GPIO
import threading
import time
import logging
from pathlib import Path
import os

ETHERNET = {
    "port0": {
        "LEDPin": "0x21:GPB0",
        "lickPin": 17,
        "SDPin":  "0x21:GPA0",
        "valvePin": "GPB0"},
    "port1": {
        "LEDPin": "0x21:GPB1",
        "lickPin": 27,
        "SDPin":  "0x21:GPA1",
        "valvePin": "GPB1"},
    "port2": {
        "LEDPin": "0x21:GPB2",
        "lickPin": 22,
        "SDPin": "0x21:GPA2",
        "valvePin": "GPB2"},
    "port3": {
        "LEDPin": "0x21:GPB3",
        "lickPin": 5,
        "SDPin": "0x21:GPA3",
        "valvePin": "GPB3"},
    "port4": {
        "LEDPin": "0x21:GPB4",
        "lickPin": 6,
        "SDPin": "0x21:GPA4",
        "valvePin": "GPB4"},
    "port5": {
        "LEDPin": "0x21:GPB5",
        "lickPin": 26,
        "SDPin": "0x21:GPA5",
        "valvePin": "GPB5"},
    "port6": {
        "LEDPin": "0x21:GPB6",
        "lickPin": 23,
        "SDPin": "0x21:GPA6",
        "valvePin": "GPB6"},
    "port7": {
        "LEDPin": "0x21:GPB7",
        "lickPin": 24,
        "SDPin": "0x21:GPA7",
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
    An interface for controlling the reward modules

    ...

    Methods:

    calibrate(pump)
    fill_lines(amounts)
    record(reset = True)
    trigger_reward(module, amount, force = False, triggered = False)
    toggle_auto_fill(on)
    change_syringe(syringeType, all = False, module = None, pump=None)
    reset_licks(module = None, lickometer = None)
    reset_all_licks()
    toggle_LED(on, module = None, led = None)
    play_tone(freq, dur, volume = 1, module = None, speaker = None)

    """

    def __init__(self, on:threading.Event, config_file = Path(__file__).parent/"config.yaml"):
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

        super(RewardInterface, self).__init__(on, config_file)

        self.pumps = {}
        self.needs_refilling = []
        # load all pumps
        for i in self.config['pumps']: 
            if 'syringeType' in self.config['pumps'][i]:
                syringe = Syringe(self.config['pumps'][i].pop('syringeType'))
            else:
                syringe = Syringe()
            self.config['pumps'][i]['syringe'] = syringe
            self.config['pumps'][i]['modePins'] = tuple(self.config['pumps'][i]['modePins'])
            self.config['pumps'][i]['parent'] = self
            self.pumps[i] = Pump(i, **self.config['pumps'][i])

        self.plugins = {}
        self.audio_interface = AudioInterface()

        # load any loose plugins not attached to a module
        if 'plugins' in self.config:
            for k, v in self.config['plugins'].items():
                plugin_type = v.pop('type')
                if plugin_type == 'Speaker':
                    self.audio_interface.add_speaker(v['name'], v['SDPin'])
                else:
                    v['parent'] = self
                    constructor = globals()[plugin_type]
                    self.plugins[k] = constructor(k, **v)

        self.modules = {}
        for i in self.config['modules']:
            if 'port' in self.config['modules'][i]:
                port = self.config['modules'][i]['port']
                self.config['modules'][i].update(ETHERNET[port])
            valvePin = self.config['modules'][i]['valvePin']
            dead_volume = self.config['modules'][i].get('dead_volume',1)
            constructor = globals()[self.config['modules'][i]['type']]
            self.modules[i] = constructor(i, self, self.pumps[self.config['modules'][i]['pump']], 
                                          valvePin, dead_volume)
            self.modules[i].load_from_config(self.config['modules'][i])

        self.valves_manually_toggled = False
        self.auto_fill = False
        self.auto_fill_thread = threading.Thread(target = self._fill_syringes)
        self.refill_check_thread = threading.Thread(target = self._check_for_refills)
    
    def start(self):
        super(RewardInterface, self).start()
        self.refill_check_thread.start() 
        self.auto_fill_thread.start()

    def calibrate(self, pump):
        """
        Set the position of a provided pump to 0

        Args:
            pump: str
                name of the pump to calibrate
        """
        self.pumps[pump].calibrate()

    def push_to_reservoir(self, pump, amount):
        """
        push a specified amount of fluid to the reservoir
        useful when changing syringes to get any air bubbles
        out
        """
        pump = self.pumps[pump]
        if pump.hasFillValve:
            fill_lock_acquired = pump.fillValve.lock.acquire(False)
            pump_lock_acquired = pump.lock.acquire(False)
            if fill_lock_acquired and pump_lock_acquired:
                for i in self.modules:
                    if self.modules[i].pump == pump:
                        self.modules[i].valve.close()
                pump.fillValve.open()
                pump.move(amount, Direction.FORWARD)
                pump.fillValve.close()
                pump.fillValve.lock.release()
                pump.lock.release()

    def empty_lines(self, modules = None):
        """
        empty the lines by drawing the dead volumes worth of
        fluid from each line hookede up to each specified module
        and push it to the reservoir.

        CAUTION: make sure the reservoir is empty before running this function

        Args:
            modules: list
                a list of all modules whose lines should be filled
            res_amount: int, dict
                either a single value specifying the amount of fluid
                to fill the lines leading up to all reservoirs with 
                or a dictionary specifying how much fluid to fill each line
                leading up to each reservoir. keys should be pump
                names and values should be amounts in mL
        
        """

        if not modules: modules = list(self.modules.keys())
        # temporarily turn off auto fill
        afill_was_on = self.auto_fill
        self.toggle_auto_fill(False)

        # get all unique pumps
        modules = list([self.modules[i] for i in modules])
        pumps = list(set([m.pump for m in modules]))
        assert all([p.hasFillValve for p in pumps]), "all pumps must have fill valves to run empty_lines"


        # pre-acquire locks for all resources and
        # make sure all valves are closed before starting
        lock_statuses = []
        for m in self.modules:
            acquired = self.modules[m].valve.lock.acquire(False)
            lock_statuses.append(acquired)
            self.modules[m].valve.close()

        # reserve all pumps
        for p in pumps: 
            acquired = p.lock.acquire(False)
            lock_statuses.append(acquired)
            acquired = p.fillValve.lock.acquire(False) 
            lock_statuses.append(acquired)    

        if all(lock_statuses):
            # empty syringe into reservoir
            for p in pumps:
                logging.debug(f'emptying syringe for pump {p.name}')
                p.fillValve.open()
                p.move(max(p.vol_left - .01 * p.syringe.volume, 0), Direction.FORWARD)
                p.fillValve.close()
            
            # empty each line
            for m in modules:
                logging.debug(f'emptying line {m.name}')
                m.empty_line()
            
            # release the locks
            for m in modules: m.valve.lock.release()
            for p in pumps:
                p.lock.release()
                p.fillValve.lock.release()
        
        self.toggle_auto_fill(afill_was_on) # turn autofill back on if it was on

    def fill_lines(self, modules = None, prime_amount = 2, res_amount = None):
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

        if not modules:
            modules = list(self.modules.keys())
        # temporarily turn off auto fill
        afill_was_on = self.auto_fill
        self.toggle_auto_fill(False)

        # get all unique pumps
        modules = list([self.modules[i] for i in modules])
        pumps = list(set([m.pump for m in modules]))

        if type(prime_amount) == int or float:
            # NOTE: we always prime all lines
            prime_amounts = {self.modules[i]: prime_amount for i in self.modules}
        elif isinstance(prime_amount, dict):
            _modules = set([self.modules[i] for i in prime_amount])
            if not len(set(modules).intersection(_modules)) == len(modules):
                raise ValueError("the keys of 'prime_amount' should be the same as the specified modules")
            prime_amounts = {self.modules[k]: v for k,v in prime_amount}
        else:
            raise TypeError(f"invalid input of type {type(prime_amount)} for argument 'prime_amount'")

        if res_amount is None:
            res_amounts = {i: prime_amount for i in pumps if i.hasFillValve}
        elif type(res_amount) == int or float:
            res_amounts = {i: res_amount for i in pumps if i.hasFillValve}
        elif isinstance(res_amount, dict):
            res_amounts = res_amount
        else:
            raise TypeError(f"invalid input of type {type(res_amount)} for argument 'res_amount'")
        
        # TODO: this portion needs to be tested
        # check if there is enough fluid in the syringes to prime the lines
        for p in pumps:
            amt = res_amounts[p]
            for m,v in prime_amounts.items():
                if m.pump == p:
                    amt += v
            if not p.is_available(amt):
                raise Exception("Not enough fluid to prime the lines")

        # pre-acquire locks for all resources and
        # make sure all valves are closed before starting
        lock_statuses = []
        for m in self.modules:
            acquired = self.modules[m].valve.lock.acquire(False)
            lock_statuses.append(acquired)
            self.modules[m].valve.close()

        # reserve all pumps
        for p in pumps: 
            acquired = p.lock.acquire(False)
            lock_statuses.append(acquired)
            if p.hasFillValve:
                acquired = p.fillValve.lock.acquire(False) 
                lock_statuses.append(acquired)    

        if all(lock_statuses):
            # prime all reservoirs
            for p, amt in res_amounts.items():
                if p.hasFillValve:
                    logging.info(f"priming reservoir for {p.name}")
                    p.fillValve.open()
                    p.move(amt, direction = Direction.FORWARD)
                    p.fillValve.close()

            # prime all lines
            for m, amt in prime_amounts.items():
                logging.info(f'priming line for {m.name}')
                m.fill_line(amt, refill = False)
            
            # refill the syringes
            for p in pumps:
                logging.info(f'refilling syringe on {p.name} with the amount used to prime the lines')
                if p.hasFillValve:
                    p.fillValve.open()
                    p.ret_to_max()
                    p.fillValve.close()
                    time.sleep(.1)

            # fill the lines for all modules
            for m in modules:
                logging.info(f'filling line for {m.name}')
                m.fill_line()
                m.valve.lock.release()

            # refill the syringes
            for p in pumps:
                logging.info(f'refilling syringe on {p.name}')
                if p.hasFillValve:
                    p.fillValve.open()
                    p.ret_to_max()
                    p.fillValve.close()
                    time.sleep(.1)
                    p.fillValve.lock.release()
                p.lock.release()

        self.toggle_auto_fill(afill_was_on) # turn autofill back on if it was on
        

    def record(self, reset = True, data_dir = None):
        """
        start a log of all events that occur on the interface,
        including any lick events or cue triggers

        Args:
            reset: bool
                whether or not to reset the lick counts on all
                lickometers before recording
        """
        if reset: self.reset_all_licks()
        super(RewardInterface, self).record(data_dir)


    def trigger_reward(self, module, amount:float, force:bool = False, trigger_mode:TriggerMode = TriggerMode.NO_TRIGGER, sync:bool = False):
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

        """
        if isinstance(trigger_mode, str):
            trigger_mode = TriggerMode[trigger_mode]
        self.modules[module].trigger_reward(amount, force = force, trigger_mode = trigger_mode, sync = sync)

    def refill_syringe(self, pump:str = None):
        """

        """

        pump_reserved = self.pumps[pump].lock.acquire(False) 
        fill_valve_reserved = self.pumps[pump].fillValve.lock.acquire(False) if self.pumps[pump].hasFillValve else True 
        if pump_reserved and fill_valve_reserved:
            try:
                for i in self.modules:
                    if i.pump.name == pump:
                        self.modules[i].valve.close()
                if self.pumps[pump].hasFillValve: self.pumps[pump].fillValve.open()
                self.pumps[pump].ret_to_max()
                self.pump.move(.05 * self.pump.syringe.mlPerCm, Direction.FORWARD)
                time.sleep(1)
                self.pump.fillValve.close()
            except BaseException as e:
                self.pumps[pump].lock.release()
                if self.pumps[pump].hasFillValve: self.pumps[pump].fillValve.lock.release()
                raise e
    
    def _check_for_refills(self):
        os.nice(19)
        while self.on.is_set():
            for i in self.pumps:
                if (i not in self.needs_refilling) and (self.pumps[i].vol_left < .95 * self.pumps[i].syringe.volume) and self.pumps[i].hasFillValve:
                    self.needs_refilling.append(i)
            time.sleep(.1)
                    

    def _fill_syringes(self):
        """
        Asynchronously fill all syringes whenever the pumps 
        are not in use. This method is not meant to be called
        directly. Use toggle_auto_fill to turn on auto-filling
        """

        while self.on.is_set():
            if self.auto_fill:
                if self.valves_manually_toggled:
                    for j in self.modules:
                        self.modules[j].valve.close()
                    self.valves_manually_toggled = False
                for i in self.needs_refilling:
                    if not self.pumps[i].enabled: 
                        self.pumps[i].enable()
                    try:
                        self.pumps[i].fillValve.open()
                        self.pumps[i].single_step(direction = Direction.BACKWARD)
                        if self.pumps[i].at_max_pos:
                            self.pumps[i].move(.05 * self.pumps[i].syringe.mlPerCm, Direction.FORWARD)
                            self.needs_refilling.remove(i)
                            self.pumps[i].fillValve.close()
                    except (ResourceLocked, EndTrackError) as e:
                        pass
            # this sleep is necessasry to avoid interfering
            # with other tasks that may want to use the pump
            # without this sleep all other threads run slower
            time.sleep(.0001)

    def toggle_auto_fill(self, on:bool):
        """
        turn auto-filling of the syringes on or off

        Args:
            on: bool
                whether or not to turn auto-filling on
        """
        if not on:
            for i in self.pumps:
                if self.pumps[i].hasFillValve:
                    try:
                        self.pumps[i].fillValve.close()
                    except ResourceLocked:
                        pass
        self.auto_fill = on

    def update_post_delay(self, post_delay:float, module:str = None):
        """
        update the post reward delay of a given module or all modules

        Args:
            post_delay: float
                desired post-reward delay
            module: str
                the module to update. if none, update all modules
        """
        if module:
            self.modules[module].post_delay = post_delay
        else:
            for m in self.modules:
                self.modules[m].post_delay = post_delay

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
                if isinstance(self.modules[module].speaker, AudioInterface.Speaker):
                    self.modules[module].speaker.play_tone(freq, dur, volume)
                else:
                    raise NoSpeaker
            else:
                raise NoSpeaker
        elif speaker is not None:
            self.audio_interface.play_tone(speaker, freq, dur, volume)
        else:
            raise ValueError("Must Specify either 'module' or 'speaker'")

    def toggle_valve(self, module:str, open_valve:bool):
        """
        toggle the valve for a given module open or close
        
        IMPORTANT NOTE: users are encouraged to use this method for controlling the valves
        instead of accessing the valves via their module and manually toggling them
        because the autofill method does not check the status of non-fill valves when refilling.
        this function ideally being the preferred method for toggling the valves automatically
        turns off auto-fill when opening a valve to avoid a refill happening when a non-fill valve is open
        we cannot gurantee against this behavior when toggling manually

        Args:
            module: str
                the name of the module with the valve to toggle
            open_valve: bool
                whether or not to open the valve
        """

        if open_valve:
            self.modules[module].valve.open()
            self.valves_manually_toggled = True
        else:
            self.modules[module].valve.close()

    def stop(self):
        if self.on.is_set(): self.on.clear()
        self.auto_fill_thread.join()
        GPIO.cleanup()