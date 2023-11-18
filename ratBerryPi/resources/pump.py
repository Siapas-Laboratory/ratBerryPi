
#######################################
# This code is influence by
# https://makersportal.com/blog/raspberry-pi-stepper-motor-control-with-nema-17
#
# Desiderio Ascencio
# Modified by: Nathaniel Nyema
#######################################

from ratBerryPi.resources.base import BaseResource, ResourceLocked
from ratBerryPi.utils import config_output
from ratBerryPi.resources.valve import Valve

import RPi.GPIO as GPIO
import time
import math
import threading
import os
import time
import pickle
from enum import Enum

#TODO: replace 'forward' and backward with this
class Direction(Enum):
    FORWARD=1
    BACKWARD=2

class EndTrackError(Exception):
    """reached end of track"""
    pass

class PumpNotEnabled(Exception):
    pass


class Syringe:
    # ID and volume for any syringes we might want to use
    # in cm and mL respectively 
    syringeTypeDict = {'BD1mL':     {'ID': 0.478, 'vol': 1}, 
                       'BD5mL':     {'ID': 1.207, 'vol': 5},
                       'BD10mL':    {'ID': 1.45,  'vol': 10},
                       'BD30mL':    {'ID': 2.17,  'vol': 30},
                       'BD50mL':    {'ID': 2.67,  'vol': 50}}

    def __init__(self, syringeType = 'BD10mL'):
        try:
            self.ID = self.syringeTypeDict[syringeType]['ID']
            self.max_pos = self.syringeTypeDict[syringeType]['vol']/(math.pi * (self.ID/2)**2)
            self.syringeType = syringeType
        except KeyError:
            msg = f"invalid syringeType '{syringeType}'. valid syringes include {[i for i in self.syringeTypeDict]}"
            raise ValueError(msg)


class Pump(BaseResource):

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
        by a DRV8825 via a raspberry pi. NOTE: we are not using RPIMotorLib
        because we needed some functionality to track the position of the pump
        but many of the provided functions are heavily inspired by RPIMotorLib
        
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
        super(Pump, self).__init__(name, None)
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
        state_dir = os.path.join(os.path.expanduser('~'), ".ratBerryPi", "pump_states")
        os.makedirs(state_dir, exist_ok = True)
        self.state_fpath = os.path.join(state_dir, f"{self.name}.pckl")

        if not os.path.exists(self.state_fpath):
            self.logger.warning(f'pump states file not found, creating and setting {self.name} position to 0')
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

        self.thread = None

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
    def position(self):
        return self._position
    
    @position.setter
    def position(self, position):
        if hasattr(self, '_position'):
            if abs(round(position,1) - round(self.position,1)) > 0:
                with open(self.state_fpath, 'wb') as f:
                    pickle.dump(self.position, f)
        self.at_min_pos = position <= 0
        self.at_max_pos = position >= self.syringe.max_pos
        self._position = position

    @property
    def vol_left(self):
        return math.pi * ((self.syringe.ID/2)**2) * self.position
    
    @property
    def stepType(self):
        return self._stepType
    
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

    def single_step(self, direction:str = None, force:bool = False):
        """
        send a single pulse to step the pump's motor in a specified direction

        Args:
        -----
        direction: str
            direction to step the motor, either forward or backward
        force: bool
            flag to force the motor to step even if the carriage sled is near the end
            of the track or the pump is not enabled
        """

        acquired = self.lock.acquire(False)
        if acquired:
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
            self.lock.release()
        else:
            raise ResourceLocked("Pump In Use")
            
    def __flush(self, channel):
        acquired = self.lock.acquire(False)
        if acquired:
            if self.verbose: self.logger.info("flushing started")
            _prev_stepType = self.stepType
            self.stepType = 'Full'
            while GPIO.input(channel)==GPIO.HIGH:
                self.single_step(direction = 'forward', force = True)
            self.stepType = _prev_stepType 
            if self.position<0: self.calibrate()
            if self.verbose: self.logger.info("flushing done")
            self.lock.release()
            
    def __reverse(self, channel):
        acquired = self.lock.acquire(False)
        if acquired:
            if self.verbose: self.logger.info("reversing started")
            _prev_stepType = self.stepType
            self.stepType = 'Full'
            while GPIO.input(channel)==GPIO.HIGH:
                self.single_step(direction = 'backward', force = True)
            self.stepType = _prev_stepType
            if self.verbose: self.logger.info("reversing done")
            self.lock.release()
    
    def is_available(self, amount, direction = 'forward'):
        if direction == 'forward':
            return amount < self.vol_left
        else:
            return amount <= (math.pi * ((self.syringe.ID/2)**2) * self.syringe.max_pos) - self.vol_left
            
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
        actual = n_steps/stepsPermL
        msg = f"{amount} mL requested; {actual} mL to be produced using stepType '{self.stepType}'; error = {amount - actual} mL"
        self.logger.debug(msg)
        return n_steps, stepsPermL

    def move(self, amount, direction, check_availability = True, 
             blocking = False, timeout = -1):
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

        acquired = self.lock.acquire(blocking = blocking, 
                                     timeout = timeout)
        if acquired:
            if direction:
                if direction != self.direction:
                    self.direction = direction
            if check_availability:
                if not self.is_available(amount, direction):
                    raise EndTrackError
            was_enabled = self.enabled
            self.enable()
            while (step_count<steps):
                try:
                    self.single_step()
                except PumpNotEnabled as e:
                    self.logger.warning(f"Pump turned off after {step_count} steps ({step_count/stepsPermL} mL)")
                    self.lock.release()
                    raise e
                step_count += 1
            
            self.lock.release()
            if not was_enabled: self.disable()
        else:
            raise ResourceLocked("Pump In Use")

    
    def ret_to_max(self, blocking = False, timeout = -1):
        if not self.at_max_pos:
            amount = (math.pi * ((self.syringe.ID/2)**2) * self.syringe.max_pos) - self.vol_left
            try:
                self.move(amount, direction = 'backward',
                          blocking = blocking, timeout = timeout)
            except EndTrackError:
                return
        else:
            raise EndTrackError

    def enable(self):
        self.enabled = True

    def disable(self):
        self.enabled = False

    def change_syringe(self, syringeType):
        """
        convenience function to change the syringe type
        """
        self.syringe = Syringe(syringeType)
        
    def __del__(self):
        with open(self.state_fpath, 'wb') as f:
            pickle.dump(self.position, f)
        if self.thread:self.thread.stop()

    def async_pump(self, amount, triggered, valve = None, direction = 'forward', 
                   close_fill = False, trigger_source = None, post_delay = 1):
        
        self.thread = Pump.PumpThread(self, amount, triggered, valve, direction,
                                           close_fill, trigger_source, post_delay)
        self.thread.start()
        # wait to check if the thread started successfully
        time.sleep(.1)
        if (not self.thread.running) and (not self.thread.success):
            try:
                raise self.thread.err
            except:
                print(self.thread.err)
    
    class PumpThread(threading.Thread):
        def __init__(self, pump, amount, triggered, valve = None, 
                    direction = 'forward', close_fill = False,
                    trigger_source = None, post_delay = 1):
            
            super(Pump.PumpThread, self).__init__()
            self.trigger_source = trigger_source
            self.valve = valve
            self.pump = pump
            self.amount = amount
            self.running = False
            self.success = False
            self.direction = direction
            self.triggered = triggered
            self.post_delay = post_delay
            self.close_fill = close_fill
            self.err = None

            if self.triggered:
                assert self.trigger_source, 'must specify trigger_source for triggered mode'
                try:
                    _ = self.trigger_source.pump_trigger
                    self.trigger_val = False
                except (AttributeError, NotImplementedError):
                    raise AttributeError('must specify property pump_trigger in trigger_source for triggered mode')
                

        def run(self):
            #pre-reserve resources so we can raise an error it they are in use
            pump_reserved = self.pump.lock.acquire(False)
            valve_reserved = self.valve.lock.acquire(False) if self.valve else True
            fill_valve_reserved = self.pump.fillValve.lock.acquire(False) if hasattr(self.pump, "fillValve") else True

            if not (pump_reserved and valve_reserved and fill_valve_reserved):
                self.running = False
                self.err = ResourceLocked("Pump In Use")
                return
            
            # pre-emptively check availability
            if not self.triggered and (not self.pump.is_available(self.amount, self.direction)):
                self.running = False
                self.err = ValueError("the requested amount is more than is available in the syringe")
                return
            
            self.running = True
            if self.triggered: 
                self.triggered_pump()
            else:
                try:
                    if self.close_fill and hasattr(self.pump, "fillValve"):
                        self.pump.fillValve.close()
                    if self.valve: self.valve.open()
                    self.pump.move(self.amount, self.direction, check_availability = False)
                    if self.valve:
                        time.sleep(self.post_delay)
                        self.valve.close()
                        self.valve.lock.release()
                    self.pump.lock.release()
                    if hasattr(self.pump, 'fillValve'): 
                        self.pump.fillValve.lock.release()
                    self.running = False
                except EndTrackError:
                    pass
            self.success = True

        def triggered_pump(self):
            # release the locks so the trigger can control them
            self.pump.lock.release()
            if self.valve: self.valve.lock.release()
            if hasattr(self.pump, 'fillValve'): self.pump.fillValve.lock.release()

            self.pump_trigger_thread = threading.Thread(target = self.trigger_pump)
            self.pump_trigger_thread.start()
            steps, _ = self.pump.calculate_steps(self.amount)
            step_count = 0
            was_enabled = self.pump.enabled
            self.pump.enable() # disable the pump until we get a trigger
            os.nice(19) # give priority to this thread
            try:
                while (step_count<steps) and self.running:
                    if self.trigger_val:
                        self.pump.lock.acquire()
                        if self.valve: 
                            self.valve.lock.acquire()
                            self.valve.open()
                        if hasattr(self.pump, 'fillValve'): 
                            self.pump.fillValve.lock.acquire()
                            self.pump.fillValve.close()
                        while self.trigger_val and (step_count<steps):
                            self.pump.single_step(direction = self.direction)
                            step_count += 1
                        if self.valve:
                            time.sleep(self.post_delay)
                            self.valve.close()
                            self.valve.lock.release()
                        self.pump.lock.release()
                        if hasattr(self.pump, 'fillValve'): 
                            self.pump.fillValve.lock.release()
            except EndTrackError:
                pass
            self.running = False
            self.pump_trigger_thread.join()
            if not was_enabled: self.pump.disable()

        def trigger_pump(self):
            prev_trigger_value = False
            while self.running:
                current_trigger_value = self.trigger_source.pump_trigger
                if prev_trigger_value != current_trigger_value:
                    if current_trigger_value:
                        if self.pump.verbose: 
                            self.pump.logger.info('pump trigger on')
                        self.trigger_val = True
                    else:
                        if self.pump.verbose: 
                            self.pump.logger.info('pump trigger off')
                        self.trigger_val = False
                    prev_trigger_value = current_trigger_value
                time.sleep(.001)

        def stop(self):
            try:
                self.pump.disable()
            except PumpNotEnabled:
                pass
            self.running = False
            self.join()
