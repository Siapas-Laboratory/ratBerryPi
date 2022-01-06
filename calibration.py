#######################################
# Copyright (c) 2021 Maker Portal LLC
# Author: Joshua Hrisko
#######################################
#
# NEMA 17 (17HS4023) Raspberry Pi Tests
# --- rotating the NEMA 17 to test
# --- wiring and motor functionality
#
# This code is influence by
# https://makersportal.com/blog/raspberry-pi-stepper-motor-control-with-nema-17
#
#######################################
#
import RPi.GPIO as GPIO
from RpiMotorLib import RpiMotorLib
import time
from time import sleep 

################################
# RPi and Motor Pre-allocations
################################
#
# define GPIO pins
GPIOPins = (6, 13, 19)
direction= 23 # Direction (DIR) GPIO Pin
step = 24 # Step GPIO Pin
EN_pin = 25 # enable pin (LOW to enable)

# Declare a instance of class pass GPIO pins numbers and the motor type
mymotortest = RpiMotorLib.A4988Nema(direction, step, GPIOPins, "DRV8825")
GPIO.setup(EN_pin,GPIO.OUT) # set enable pin as output

###########################
# Actual motor control
###########################

GPIO.output(EN_pin,GPIO.LOW) # pull enable to low to enable motor
numberOfSteps = 44 #200 steps in one revoltion for FULL step type 
backSteps = 40000
stepDelay = .001
pulseSteps = 1000
loopNumber = 50
stepType = "Half" #Full, Half, 1/4, 1/8, 1/16, 1/32

# Functions 
def pulseForward(pulseSteps, stepDelay, stepType):
    print("Pulsing the motor forward")
    mymotortest.motor_go(False, # True=Clockwise - Back, False=Counter-Clockwise - Forward
                    stepType, # Step type (Full,Half,1/4,1/8,1/16,1/32)
                    pulseSteps, # number of steps
                    stepDelay, # step delay [sec]
                    False, # True = print verbose output 
                    .05) # initial delay [sec]

def pulseBack(pulseSteps, stepDelay, stepType):
    print("Pulsing the motor back")
    mymotortest.motor_go(True, # True=Clockwise - Back, False=Counter-Clockwise - Forward
                    stepType, # Step type (Full,Half,1/4,1/8,1/16,1/32)
                    pulseSteps, # number of steps
                    stepDelay, # step delay [sec]
                    False, # True = print verbose output 
                    .05) # initial delay [sec]

def returnToInitialPoint(backSteps, stepDelay, stepType):
    print("Motor is returning back to initial point... ")
    sleep(5)
    mymotortest.motor_go(True, # True=Clockwise - Back, False=Counter-Clockwise - Forward
                         stepType, # Step type (Full,Half,1/4,1/8,1/16,1/32)
                          backSteps, # number of steps
                         stepDelay, # step delay [sec]
                         False, # True = print verbose output 
                         .05) # initial delay [sec]
    sleep(5)
    mymotortest.motor_go(True, # True=Clockwise - Back, False=Counter-Clockwise - Forward
                     stepType, # Step type (Full,Half,1/4,1/8,1/16,1/32)
                      backSteps, # number of steps
                     stepDelay, # step delay [sec]
                     False, # True = print verbose output 
                     .05) # initial delay [sec]

def runMotor(numberOfSteps, stepDelay, loopNumber, stepType):
    print("Motor is running... ")
    for i in range(loopNumber):
        sleep(1)
        mymotortest.motor_go(False, # True=Clockwise - Back, False=Counter-Clockwise - Forward
                             stepType, # Step type (Full,Half,1/4,1/8,1/16,1/32)
                             numberOfSteps, # number of steps
                             stepDelay, # step delay [sec]
                             False, # True = print verbose output 
                             .05) # initial delay [sec]
         
    
# Running the program

inVal = input("Enter [b] to pulse back\nEnter [p] to pulse \n\n Enter [s] to begin program: ")

while (inVal is "b") or (inVal is "p") or (inVal is "s"):
    while inVal is "b":
        pulseBack(pulseSteps, stepDelay, stepType)
        inVal = input("Enter [b] to pulse back\nEnter [p] to pulse forward\nEnter [s] to begin program\nEnter [x] to exit: ")

    while inVal is "p":
        pulseForward(pulseSteps, stepDelay, stepType)
        inVal = input("Enter [b] to pulse back\nEnter [p] to pulse\nEnter [s] to begin program\nEnter [x] to exit: ")

    while inVal is "s":
        runMotor(numberOfSteps, stepDelay, loopNumber, stepType)   
        #returnToInitialPoint(backSteps, stepDelay, stepType)
        inVal = input("Enter [b] to pulse back\nEnter [p] to pulse\nEnter [s] to begin program\nEnter [x] to exit: ")
              
              
    #bug where if enter p at the b loop, it exits because its while loop is above 
print("Program ended")          
        

    

GPIO.cleanup() # clear GPIO allocations after run

