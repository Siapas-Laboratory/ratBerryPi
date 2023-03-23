
#######################################
# This code is influence by
# https://makersportal.com/blog/raspberry-pi-stepper-motor-control-with-nema-17
#
# Desiderio Ascencio 
#######################################



import RPi.GPIO as GPIO
from RpiMotorLib import RpiMotorLib
import time
from time import sleep
import numpy as np
import inspect
import pandas as pd
import threading

################################
# RPi and Motor Pre-allocations
################################


class Syringe:
    
    stepsTypeDict = {"Full":200, 
                      "Half":400,
                      "1/4":800,
                      "1/8": 1600,
                      "1/16": 3200}

    syringeTypeDict = {'BD1mL': 0.478, 
                       'BD5mL': 1.207}
    
    def __init__(self, stepPin, syringeType = None, stepType = None, ID = None, 
                 ENPin = 25, dirPin = 23, GPIOPins = (6, 13, 19), tolerance = 1e-4):
        
        """
        this is a class that allows for the control of a syringe
        pump actuated by a Nema 17 Bipolar stepper motor and driven
        by a DRV8825 via a raspberry pi.
        
        Args:
        -----
            stepPin: int
                pin on the pi that is wired to the step pin of
                the DRV8825 controlling this pump
            syringeType: str, optional
                a string denoting any of the syringes for which
                we already have inner diameters for
                if this field is not set you must set the ID
            stepType: str, optional
                any of the available step types for driving the motor.
                either Full, Half, 1/4, 1/8, or 1/16
            ID: float, optional
                inner diameter of the syringe. if this is not
                specified you must chosed a prest syringeType
            ENPin: int, optional
                pin for enabling the use of the pump
            dirPin: int, optional
                pin to set the direction of the pump
            GPIOPins: tuple(int, int, int)
                the pins used to set the step type (M0, M1, M2)
            tolerance: float
                the allowable error in the amount of fluid delivered in mL
        """
        
        
        if syringeType is not None:
            if ID is not None:
                print("warning: both syringeType and ID provided, using syringeType to calculate ID")
            self.syringeType = syringeType
        else:
            self.ID = ID
        
        self.stepType = stepType
        self.stepDelay = .001 
        self.tolerance = tolerance
        self.green_ligt = True
        
        # Declare a instance of class pass GPIO pins numbers and the motor type
        self.mymotor = RpiMotorLib.A4988Nema(dirPin , stepPin , GPIOPins, "DRV8825")
        GPIO.setup(ENPin,GPIO.OUT) # set enable pin as output
        GPIO.output(ENPin,GPIO.LOW)
        
    @property
    def syringeType(self):
        return self._syringeType
    
    @syringeType.setter
    def syringeType(self, a):
        # check if we have an ID for
        # the specified syringe type
        if a in self.syringeTypeDict:
            self.ID = self.syringeTypeDict[a]
            self._syringeType = a    
        elif a is not None:
            raise ValueError(f"invalid syringeType '{a}'. valid syringes include {[i for i in self.syringeTypeDict]}")    
        
    @property
    def ID(self):
        return self._ID
    
    @ID.setter
    def ID(self, a):
        self._ID = a
        self.getConversionFactor()
        curframe = inspect.currentframe()
        calframe = inspect.getouterframes(curframe, 2)
        if calframe[1][3] != 'syringeType':
            # if this isn't being called through the setter method
            # for syringeType set syringeType to None
            # for clarity we want to make sure syringeType is only set
            # if we intend to use an preset ID based on the value
            self.syringeType = None
        
    @property
    def stepType(self):
        return self._stepType
    
    @stepType.setter
    def stepType(self, a):
        if (a in self.stepsTypeDict) or (a is None):
            self._stepType = a
            self._eff_stepType = a
        else:
            raise ValueError(f"invalid step type. valid stepTypes include {[i for i in self.stepsTypeDict]}")       
            
    def getConversionFactor(self):
        """
        calculate volume dispensed in mL
        per revolution of the motor
        """
        if self.ID is not None:
            mlPerCm = np.pi * ((self.ID/2)**2)
            pitch = 0.08 # pitch in cm of the threads on the rod attached to the motor
            #              assuming a single start threaded bearing this is equivalent to the lead,
            #              the distance in cm the pump moves per turn of the motor
            self.mlPerThread = mlPerCm * pitch
        
    def calculateSteps(self, amount):
        """
        calculate the numer of steps of the motor
        needed to dispense a given amount of fluid
        
        Args:
        -----
        amount: float
            desired fluid output in mL
        """
        if self.stepType is None:
            # if no stepType is specified use the coarsest one
            # that gets us within some tolerance of the desired output
            stepsPerThread = pd.Series(self.stepsTypeDict)
            stepsPerMl = (stepsPerThread/ self.mlPerThread)
            n_steps = stepsPerMl * amount
            # check the error for all possible step types
            ok = (n_steps.round()/stepsPerMl - amount).abs() < self.tolerance
            if ok.sum() >0:
                self._eff_stepType = n_steps.index[(n_steps.round()/stepsPerMl - amount).abs()<self.tolerance][0]
            else:
                # if no step types meet the tolerance criteria use 1/16
                self._eff_stepType = '1/16'
                print(f"warning: no step types meet the desired tolerance ({self.tolerance} mL), consider using a different syringe or set a higher tolerance. setting step type to 1/16")
            n_steps = n_steps[self._eff_stepType]
        else:
            stepsPerThread = self.stepsTypeDict[self.stepType]
            n_steps = (stepsPerThread/ self.mlPerThread) * amount
        return int(round(n_steps))

    def pulseForward(self, amount):
        """
        push out a given amount of fluid
        from the syringe
        
        Args:
        -----
        amount: float
            desired fluid output in mL
        """
        print("Pulsing the motor forward...")
        steps = self.calculateSteps(amount)
        print("Steps is: ", steps, "using step type: ", self._eff_stepType)
        step_count = 0
        while step_count<steps:
            if self.green_light:
                self.mymotor.motor_go(clockwise=False, steptype=self._eff_stepType, 
                                      steps=1, stepdelay=self.stepDelay, 
                                      verbose=False, initdelay=0) 
                step_count += 1
        return 'done'
             
        
    def pulseBackward(self, amount):
        """
        pull in a given amount of fluid
        from the syringe
        
        Args:
        -----
        amount: float
            desired fluid output in mL
        """
        print("Pulsing the motor forward...")
        steps = self.calculateSteps(amount)
        print("Steps is: ", steps, "using step type: ", self._eff_stepType)
        
        self.mymotor.motor_go(clockwise=True, teptype=self._eff_stepType, 
                              steps=steps, stepdelay=self.stepDelay, 
                              verbose=False, initdelay=0)



