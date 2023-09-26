
#######################################
# This code is influence by
# https://makersportal.com/blog/raspberry-pi-stepper-motor-control-with-nema-17
#
# Desiderio Ascencio
# Modified by: Nathaniel Nyema
#######################################

from ratBerryPi.utils import config_output
from ratBerryPi.plugins.valve import Valve

import RPi.GPIO as GPIO
import time
import math
import threading
import os
import time
import pickle
import logging
from pathlib import Path


class EndTrackError(Exception):
    """reached end of track"""
    pass

class PumpNotEnabled(Exception):
    pass

class PumpInUse(Exception):
    pass

class Syringe:
    #TODO: determine max_pos for all possible syringes
    syringeTypeDict = {'BD1mL':     {'ID': 0.478, 'max_pos': 0}, 
                       'BD5mL':     {'ID': 1.207, 'max_pos': 4.7},
                       'BD10mL':    {'ID': 1.45,  'max_pos': 6.5},
                       'BD30mL':    {'ID': 2.17,  'max_pos': 0},
                       'BD50/60mL': {'ID': 2.67,  'max_pos': 0}}

    def __init__(self, syringeType = 'BD10mL'):
        try:
            self.ID = self.syringeTypeDict[syringeType]['ID']
            self.max_pos = self.syringeTypeDict[syringeType]['max_pos']
            self.syringeType = syringeType
        except KeyError:
            msg = f"invalid syringeType '{syringeType}'. valid syringes include {[i for i in self.syringeTypeDict]}"
            raise ValueError(msg)


class Pump:

    step_type_configs = {'Full': (False, False, False),
                         'Half': (True,  False, False),
                         '1/4':  (False, True,  False),
                         '1/8':  (True,  True,  False),
                         '1/16': (False, False, True),
                         '1/32': (True,  False, True)}
    
    steps_per_rot = {"Full":200, 
                      "Half":400,
                      "1/4":800,
                      "1/8": 1600,
                      "1/16": 3200}
    
    def __init__(self, name, stepPin, flushPin, revPin, modePins, dirPin, fillValvePin = None, 
                 endPin = None, syringe = Syringe(syringeType='BD5mL'), stepDelay = .0005,
                 stepType = "Half", pitch = 0.08,  reset = False, verbose = True):
        
        """
        this is a class that allows for the control of a syringe
        pump actuated by a Nema 17 Bipolar stepper motor and driven
        by a DRV8825 via a raspberry pi.
        
        Args:
        -----
            _stepPin: int
                pin on the pi that is wired to the step pin of
                the DRV8825 controlling this pump
            stepType: str, optional
                any of the available step types for driving the motor.
                either Full, Half, 1/4, 1/8, or 1/16
            _dirPin: int, optional
                pin to set the direction of the pump
            GPIOPins: tuple(int, int, int)
                the pins used to set the step type (M0, M1, M2)
            tolerance: float
                the allowable error in the amount of fluid delivered in mL
        """

        self.name = name
        self.syringe = syringe

        self._dirPin = config_output(dirPin)
        self.direction = 'forward'

        self._stepPin = config_output(stepPin)
        self._modePins = (config_output(modePins[0]),
                         config_output(modePins[1]),
                         config_output(modePins[2]))
        self.stepType = stepType
        
        self.stepDelay = stepDelay
        self.pitch = pitch
        self.enabled = False
        self.in_use = False
        self.verbose = verbose
        state_dir = "~/.ratBerryPi/pump_states"
        os.makedirs(state_dir, exist_ok = True)
        self.state_fpath = os.path.join(state_dir, f"{self.name}.pckl")

        if not os.path.exists(self.state_fpath):
            logging.warning(f'pump states file not found, creating and setting {self.name} position to 0')
            self.position = 0
            with open(self.state_fpath, 'wb') as f:
                pickle.dump(self.position, f)
        else:
            with open(self.state_fpath, 'rb') as f:
                saved_pos = pickle.load(f)
            if not reset:
                self.position = saved_pos
            else:
                self.position = 0
                with open(self.state_fpath, 'wb') as f:
                    pickle.dump(self.position, f)
        
        # add event detection for the flush pin
        GPIO.setup(flushPin, GPIO.IN, pull_up_down = GPIO.PUD_DOWN)
        GPIO.add_event_detect(flushPin, GPIO.RISING, callback = self.__flush)
        
        # add event detection for the reverse pin
        GPIO.setup(revPin, GPIO.IN, pull_up_down = GPIO.PUD_DOWN)
        GPIO.add_event_detect(revPin, GPIO.RISING, callback = self.__reverse)

        if endPin is not None:
            # add event detection for the end pin
            GPIO.setup(endPin, GPIO.IN, pull_up_down = GPIO.PUD_DOWN)
            GPIO.add_event_detect(endPin, GPIO.RISING, callback = self.calibrate)

        if fillValvePin is not None:
            self.fillValve = Valve(f'{self.name}-fillValve', self, fillValvePin)

    @property
    def direction(self):
        return self._direction
    
    @direction.setter
    def direction(self, direction):
        if not isinstance(direction, str):
            raise ValueError("direction must be of type str")
        if not direction.lower() in ['forward', 'backward']:
            raise ValueError("direction must be either 'forward' or 'backward'")
        self._direction = direction.lower()
        self._dirPin.value = direction.lower() == 'forward'
        time.sleep(.01)

    @property
    def syringe(self):
        return self._syringe

    @syringe.setter
    def syringe(self, syringe):
        assert isinstance(syringe, Syringe), 'syringe must be an instance of Syringe'
        self._syringe = syringe

    @property
    def stepType(self):
        return self._stepType
    
    @property
    def position(self):
        return self._position
    
    @property
    def vol_left(self):
        return math.pi * ((self.syringe.ID/2)**2) * self.position
    
    @position.setter
    def position(self, position):
        if hasattr(self, '_position'):
            if abs(round(position,1) - round(self.position,1)) > 0:
                with open(self.state_fpath, 'wb') as f:
                    pickle.dump(self.position, f)
        self.at_min_pos = position <= 0
        self.at_max_pos = position >= self.syringe.max_pos
        self._position = position
    
    @stepType.setter
    def stepType(self, stepType):
        if stepType in self.step_type_configs:
            self._stepType = stepType
            self._modePins[0].value = self.step_type_configs[stepType][0]
            self._modePins[1].value = self.step_type_configs[stepType][1]
            self._modePins[2].value = self.step_type_configs[stepType][2]
            time.sleep(.01)
        else:
            raise ValueError(f"invalid step type. valid stepTypes include {[i for i in self.step_type_configs]}")

    def calibrate(self, channel=None):
        self.position = 0
        self.track_end = True

    def get_conversion(self, stepType = None):
        stepType = stepType if stepType is not None else self.stepType
        stepsPerThread = self.steps_per_rot[stepType]
        mlPerCm = math.pi * ((self.syringe.ID/2)**2)
        mlPerThread = mlPerCm * self.pitch
        return  stepsPerThread/ mlPerThread

    def single_step(self, direction = None, force = False):
        if direction:
            if direction != self.direction:
                self.direction = direction
        too_close = self.at_min_pos and self.direction == 'forward'
        too_far = self.at_max_pos and self.direction != 'forward'
        if (too_close or too_far) and not force:
            raise EndTrackError      
        if (not force) and (not self.enabled):
            raise PumpNotEnabled 

        self._stepPin.value = True
        time.sleep(self.stepDelay)
        self._stepPin.value = False
        time.sleep(self.stepDelay)

        if self.direction == 'forward':
            self.position -= (self.pitch/self.steps_per_rot[self.stepType])
        else:
            self.position += (self.pitch/self.steps_per_rot[self.stepType])
            
    def __flush(self, channel):
        if not self.in_use:
            if self.verbose: logging.info("flushing")
            _prev_stepType = self.stepType
            self.reserve(stepType = 'Full')
            while GPIO.input(channel)==GPIO.HIGH:
                self.single_step(direction = 'forward', force = True)
            self.unreserve()
            self.stepType = _prev_stepType 
            if self.position<0:
                self.calibrate()
            if self.verbose: logging.info("done")
            
    def __reverse(self, channel):
        if not self.in_use:
            if self.verbose: logging.info("reversing")
            _prev_stepType = self.stepType
            self.reserve(stepType = 'Full')
            while GPIO.input(channel)==GPIO.HIGH:
                self.single_step(direction = 'backward', force = True)
            self.unreserve()
            self.stepType = _prev_stepType
            if self.verbose: logging.info("done")
    
    def is_available(self, amount):
        return amount < self.vol_left
            
    def calculate_steps(self, amount):
        """
        calculate the numer of steps of the motor
        needed to dispense a given amount of fluid
        
        Args:
        -----
        amount: float
            desired fluid output in mL
        """
        stepsPermL = self.get_conversion()
        n_steps = int(round(stepsPermL * amount))
        if self.verbose:
            actual = n_steps/stepsPermL
            msg = f"{amount} mL requested; {actual} mL to be produced using stepType '{self.stepType}'; error = {amount - actual} mL"
            logging.info(msg)
        return n_steps, stepsPermL

    def move(self, amount, direction, unreserve = True, 
             force = False, pre_reserved = False, check_availability = True):
        """
        move a given amount of fluid out of or into the syringe
        
        Args:
        -----
        amount: float
            desired fluid output in mL
        forward: bool
            whether or not to move the piston forward
        """
        steps, stepsPermL = self.calculate_steps(amount)
        step_count = 0

        if not pre_reserved:
            self.reserve(force = force)
        if direction:
            if direction != self.direction:
                self.direction = direction
        if self.direction == 'forward' and check_availability:
            if not self.is_available(amount):
                raise EndTrackError
        was_enabled = self.enabled
        self.enable()
        while (step_count<steps):
            try:
                self.single_step(force = force)
            except EndTrackError as e:
                logging.debug(f"End reached after {step_count} steps ({step_count/stepsPermL} mL)")
                self.unreserve()
                raise e
            except PumpNotEnabled as e:
                logging.debug(f"Pump turned off after {step_count} steps ({step_count/stepsPermL} mL)")
                self.unreserve()
                raise e
            step_count += 1
        
        if unreserve:
            self.unreserve()
        if not was_enabled:
            self.disable()
    
    def ret_to_max(self, unreserve = True, force = False, pre_reserved = False):
        if not self.at_max_pos:
            amount = (math.pi * ((self.syringe.ID/2)**2) * self.syringe.max_pos) - self.vol_left
            try:
                self.move(amount, direction = 'backward', unreserve = unreserve, 
                          force = force, pre_reserved = pre_reserved)
            except EndTrackError:
                return
        else:
            raise EndTrackError

    def enable(self):
        self.enabled = True

    def disable(self):
        self.enabled = False

    def reserve(self, stepType = None, force = True):
        if self.in_use:
            if not force:
                raise PumpInUse
        if stepType and (stepType != self.stepType):
            self.stepType = stepType
        self.in_use = True

    def unreserve(self):
        self.in_use = False         

    def change_syringe(self, syringeType):
        """
        convenience function to change the syringe type
        """
        self.syringe = Syringe(syringeType)
        
    def __del__(self):
        with open(self.state_fpath, 'wb') as f:
            pickle.dump(self.position, f)



class PumpThread(threading.Thread):
    def __init__(self, pump, amount, triggered, valve = None, direction = 'forward', close_fill = False, 
                 parent = None, force = False, post_delay = 1, stepType = None):
        super(PumpThread, self).__init__()
        self.parent = parent
        self.valve = valve
        self.pump = pump
        self.amount = amount
        self.running = False
        self.direction = direction
        self.status = 0
        self.triggered = triggered
        self.force = force
        self.post_delay = post_delay
        self.stepType = stepType if stepType else self.pump.stepType
        self.close_fill = close_fill
        if self.triggered:
            assert self.parent, 'must specify parent triggered mode'
            try:
                _ = self.parent.pump_trigger
            except AttributeError:
                raise AttributeError('must specify property pump_trigger in parent for triggered mode')
            
    def start(self):
        # try to reserve the pump before spawning the thread
        # so we can throw an error if necessary
        self.pump.reserve(force = self.force, stepType = self.stepType)
        if self.close_fill and hasattr(self.pump, "fillValve"):
            self.pump.fillValve.close()
        # pre-emptively check availability
        if not self.force and (not self.pump.is_available(self.amount)):
            raise EndTrackError
        super(PumpThread, self).start()

    def run(self):
        if self.valve: self.valve.open()
        self.running = True
        self.status = 1
        if self.triggered:
            self.triggered_pump()
        else:
            try:
                self.pump.move(self.amount, self.direction, pre_reserved = True,
                               check_availability = False, force = self.force, unreserve = False)
                self.running = False
            except EndTrackError:
                self.status = -1
                pass
        if self.valve:
            time.sleep(self.post_delay)
            self.valve.close()
        self.status = 2
        self.pump.unreserve()

    def triggered_pump(self):
        self.pump_trigger_thread = threading.Thread(target = self.trigger_pump)
        self.pump_trigger_thread.start()
        steps, stepsPermL = self.pump.calculate_steps(self.amount)
        step_count = 0
        was_enabled = self.pump.enabled
        self.pump.disable() # disable the pump until we get a trigger
        os.nice(19) # give priority to this thread
        while (step_count<steps) and self.running:
            try:
                self.pump.single_step(self.direction)
                step_count += 1
            except EndTrackError:
                self.status = -1
                break
            except PumpNotEnabled:
                pass
        self.running = False
        self.pump_trigger_thread.join()
        if was_enabled:
            self.pump.enable()
        else:
            self.pump.disable()

    def trigger_pump(self):
        prev_trigger_value = False
        while self.running:
            current_trigger_value = self.parent.pump_trigger
            if prev_trigger_value != current_trigger_value:
                if current_trigger_value:
                    if self.pump.verbose: logging.info('pump trigger on')
                    self.pump.enable()
                else:
                    if self.pump.verbose: logging.info('pump trigger off')
                    self.pump.disable()
                prev_trigger_value = current_trigger_value
            time.sleep(.001)

    def stop(self):
        try:
            self.pump.disable()
        except PumpNotEnabled:
            pass
        self.running = False
        self.join()
