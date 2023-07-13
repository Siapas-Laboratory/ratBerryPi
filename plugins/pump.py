
#######################################
# This code is influence by
# https://makersportal.com/blog/raspberry-pi-stepper-motor-control-with-nema-17
#
# Desiderio Ascencio
# Modified by: Nathaniel Nyema
#######################################



import RPi.GPIO as GPIO
from RpiMotorLib import RpiMotorLib
import time
from time import sleep
import numpy as np
import inspect
import pandas as pd
import threading
import sys
sys.path.append("../")
from utils import *
import os

################################
# RPi and Motor Pre-allocations
################################

class Syringe:
    syringeTypeDict = {'BD1mL': 0.478, 
                       'BD5mL': 1.207,
                       'BD10mL': 1.45,
                       'BD30mL': 2.17,
                       'BD50/60mL': 2.67}

    def __init__(self, syringeType = None, ID = None):
        assert (int(syringeType is None) + int(ID is None))==1, "exactly one of inputs syringeType or ID should be specified "
        if syringeType is not None:
            self.ID = self.get_syringe_ID(syringeType)
        else:
            self.ID = ID

    def get_syringe_ID(self, syringeType):
        try:
            ID = self.syringeTypeDict[syringeType]
            return ID
        except KeyError:
            msg = f"invalid syringeType '{a}'. valid syringes include {[i for i in self.syringeTypeDict]}"
            raise ValueError(msg)
    def __repr__(self):
        return f"Syringe(ID={self.ID})"

class Pump:
    
    stepTypeDict = {"Full":200, 
                      "Half":400,
                      "1/4":800,
                      "1/8": 1600,
                      "1/16": 3200}
    
    def __init__(self, stepPin, flushPin, revPin, GPIOPins, dirPin, 
                 endPin = None, syringe = Syringe(syringeType='BD5mL'), 
                 stepType = "Half", pitch = 0.08, track_length = 10):
        
        """
        this is a class that allows for the control of a syringe
        pump actuated by a Nema 17 Bipolar stepper motor and driven
        by a DRV8825 via a raspberry pi.
        
        Args:
        -----
            stepPin: int
                pin on the pi that is wired to the step pin of
                the DRV8825 controlling this pump
            stepType: str, optional
                any of the available step types for driving the motor.
                either Full, Half, 1/4, 1/8, or 1/16
            dirPin: int, optional
                pin to set the direction of the pump
            GPIOPins: tuple(int, int, int)
                the pins used to set the step type (M0, M1, M2)
            tolerance: float
                the allowable error in the amount of fluid delivered in mL
        """
        

        self.syringe = syringe
        self.stepType = stepType
        self.stepDelay = .0005 
        self.pitch = pitch
        self.enabled = False
        self.in_use = False
        self.position = None
        self.track_length = track_length
        
        # Declare a instance of class pass GPIO pins numbers and the motor type
        self.mymotor = RpiMotorLib.A4988Nema(dirPin , stepPin , GPIOPins, "DRV8825")
        
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
    
    @stepType.setter
    def stepType(self, stepType):
        if stepType in self.stepTypeDict:
            self._stepType = stepType
        else:
            raise ValueError(f"invalid step type. valid stepTypes include {[i for i in self.stepTypeDict]}")

    def calibrate(self, channel):
        self.position = 0

    def get_conversion(self, stepType = None):
        stepType = stepType if stepType is not None else self.stepType
        stepsPerThread = self.stepTypeDict[stepType]
        mlPerCm = np.pi * ((self.syringe.ID/2)**2)
        mlPerThread = mlPerCm * self.pitch
        return  stepsPerThread/ mlPerThread

    def single_step(self, forward, stepType, force = False):
        clockwise = not forward
        if self.track_end(forward) and not force:
            raise EndTrackError
        if (not force) and (not self.enabled):
            raise PumpNotEnabled
        
        self.mymotor.motor_go(clockwise=clockwise, steptype=stepType, 
                            steps=1, stepdelay=self.stepDelay, 
                            verbose=False, initdelay=0)
        if self.position is not None:
            if forward:
                self.position -= (self.pitch/self.stepTypeDict[stepType])
            else:
                self.position += (self.pitch/self.stepTypeDict[stepType])
            
    def __flush(self, channel):
        if not self.in_use:
            print("flushing")
            self.in_use = True
            while GPIO.input(channel)==GPIO.HIGH:
                self.single_step(True, "Full", force = True)
            self.in_use = False
            print("done")
            
    def __reverse(self, channel):
        if not self.in_use:
            print("reversing")
            self.in_use = True
            while GPIO.input(channel)==GPIO.HIGH:
                self.single_step(False, "Full", force = True)
            self.in_use = False
            print("done")

            
    def calculate_steps(self, amount, verbose = False):
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
        if verbose:
            actual = n_steps*stepsPermL
            msg = f"{amount} mL requested; {actual} mL to be produced using stepType '{self.stepType}'; error = {amount - actual} mL"
            print(msg)
        return n_steps, stepsPermL

    def move(self, amount, forward, verbose = False):
        """
        move a given amount of fluid out of or into the syringe
        
        Args:
        -----
        amount: float
            desired fluid output in mL
        forward: bool
            whether or not to move the piston forward
        verbose: bool
            whether or not to print
        """
        steps, stepsPermL = self.calculate_steps(amount, verbose)
        step_count=0
        self.in_use = True
        while (step_count<steps):
            try:
                self.single_step(forward, self.stepType)
            except EndTrackError as e:
                print(f"End reached after {step_count} steps ({step_count/stepsPermL} mL)")
                self.in_use = False
                raise e
            except PumpNotEnabled as e:
                print(f"Pump turned off after {step_count} steps ({step_count/stepsPermL} mL)")
                self.in_use = False
                raise e
            step_count += 1
        self.in_use = False

    def track_end(self, forward):
        if self.position is not None:
            if ((self.position<=0) and forward) or ((self.position>=self.track_length) and not forward):
                return  True
            else:
                return False
        else:
            return False

    def enable(self):
        self.enabled = True

    def disable(self):
        self.enabled = False             

    def change_syringe(self, syringeType = None, ID = None):
        """
        convenience function to change the syringe type
        """
        self.syringe = Syringe(syringeType, ID)



class PumpThread(threading.Thread):
    def __init__(self, pump, amount, triggered, valvePin = None, forward = True, parent = None):
        super(PumpThread, self).__init__()
        self.parent = parent
        self.valvePin = valvePin
        self.pump = pump
        self.amount = amount
        self.running = False
        self.forward = forward
        self.status = 0
        self.triggered = triggered
        if self.triggered:
            assert self.parent, 'must specify parent triggered mode'
            try:
                _ = self.parent.pump_trigger
            except AttributeError:
                raise AttributeError('must specify property pump_trigger in parent for triggered mode')

    def run(self):
        if self.valvePin: GPIO.output(self.valvePin, GPIO.HIGH)
        self.running = True
        self.status = 1
        if self.triggered:
            self.triggered_pump()
        else:
            try:
                self.pump.enable()
                self.pump.move(self.amount, self.forward)
                self.running = False
            except EndTrackError:
                self.status = -1
                pass
        self.pump.disable()
        if self.valvePin is not None: GPIO.output(self.valvePin, GPIO.LOW)
        self.status = 2

    def triggered_pump(self):
        self.pump_trigger_thread = threading.Thread(target = self.trigger_pump)
        self.pump_trigger_thread.start()
        steps, stepsPermL = self.pump.calculate_steps(self.amount)
        step_count = 0
        self.pump.in_use = True # reserve the pump
        self.pump.disable() # disable the pump until we get a trigger
        os.nice(19) # give priority to this thread
        while (step_count<steps) and self.running:
            try:
                self.pump.single_step(self.forward, self.pump.stepType)
                step_count += 1
            except EndTrackError:
                self.status = -1
                break
            except PumpNotEnabled:
                pass
        self.pump.in_use = False
        self.running = False
        self.pump_trigger_thread.join()

    def trigger_pump(self):
        prev_trigger_value = False
        print('off')
        while self.running:
            current_trigger_value = self.parent.pump_trigger
            if prev_trigger_value != current_trigger_value:
                if current_trigger_value:
                    print('on')
                    self.pump.enable()
                else:
                    print('off')
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