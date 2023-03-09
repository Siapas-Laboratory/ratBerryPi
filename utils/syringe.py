
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

################################
# RPi and Motor Pre-allocations
################################


class syringe:
    def __init__(self, syringeType,  stepPin ,
                 stepType = "Half", # controls the resolution of stepping. maybe this can be set dynamically?
                 ENPin = 25, dirPin = 23, GPIOPins = (6, 13, 19)):
        self.syringeType = syringeType
        self.stepDelay = .001 # what does this do?
        self.stepType = stepType
        self.ENPin = ENPin # enable pin (LOW to enable)
        
        # Declare a instance of class pass GPIO pins numbers and the motor type
        self.mymotor = RpiMotorLib.A4988Nema(dirPin , stepPin , GPIOPins, "DRV8825")
        GPIO.setup(ENPin,GPIO.OUT) # set enable pin as output
        GPIO.output(ENPin,GPIO.LOW)

    def calculateSteps(self, amount):
        # TODO: I want this function to be a bit more flexible
        # should take as input some calibration info or the
        # syringe diameter and use this to calculate number of steps

        if "3" in self.syringeType:
            dist = .555625 #distance bw .1 mL in cm 

        else:
            dist = .174625 #distance bw .1 mL in cm

        #catch for case of not thick or thin

        # --------- Calculation Note -----------
        # For threadsPerCm, there are 32 threads per inch,
        # and so I converted the 1 inch to cm and so I
        # multiplied the 32 x .393701 to get 12.598432
        threadsPerCm = 12.598432 #threads in 1 cm distance
        # Calculating the linear distance syringe should move 
        #create code for mililiters
        multFactor = amount / .1 #amount mL div by .1 mL 
        linDist = dist * multFactor
        # Calculating how many steps should take to travel linear distance
        threadsLinDist = threadsPerCm * linDist

        stepsTypeDict = {"Full":200,
                          "Half":400,
                          "1/4":800,
                          "1/8": 1600,
                          "1/16": 3200}
        stepsPerThread = stepsTypeDict[self.stepType] #steps per revolution, which is the same as thread
        finalSteps = round(stepsPerThread * threadsLinDist) # gets you steps to achieve the distance 
        return finalSteps


    def pulseForward(self, amount):
        print("Pulsing the motor forward...")
        steps = self.calculateSteps(amount)
        print("Steps is: ", steps)
        self.mymotor.motor_go(False, # True=Clockwise - Back, False=Counter-Clockwise - Forward
                        self.stepType, # Step type (Full,Half,1/4,1/8,1/16,1/32)
                        steps, # number of steps
                        self.stepDelay, # step delay [sec]
                        False, # True = print verbose output 
                        .05) # initial delay [sec]





