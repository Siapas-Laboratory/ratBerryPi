
#######################################
# This code is influence by
# https://makersportal.com/blog/raspberry-pi-stepper-motor-control-with-nema-17
#
# Desiderio Ascencio 
#######################################

import FakeRPi.GPIO as GPIO

import RPi.GPIO as GPIO
from RpiMotorLib import RpiMotorLib
import time
from time import sleep 

################################
# RPi and Motor Pre-allocations
################################


class syringe:

	def __init__(self, units, amount, syringeType):
		self.units = units 
		self.amount = amount
		self.syringeType = syringeType
		self.stepDelay = .001
		self.stepType = "Half"
		self.loopNumber = 100
		self.reward = False #might not be neccessary property
		self.waterCounter = 0 

	def calculateSteps(self):

		amount = self.amount 
		units = self.units 
		syringeType = self.syringeType 
		stepType = self.stepType 
		
		if "3" in syringeType:
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
		if units == "microliters":
			multFactor = amount / 100 #the 100 is 100 microliters in .1 mL
			linDist = dist * multFactor #how much the syringe will linearly move in cm
									   #for an amount in microLiters
		else:
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
		stepsPerThread = stepsTypeDict[stepType] #steps per revolution, which is the same as thread
		finalSteps = round(stepsPerThread * threadsLinDist) # gets you steps to achieve the distance 
		return finalSteps


	def syringeGPIOInit(self): 

		"""
		I believe this code below can be included into the initialization function above,
		just needs to be run once and the motor can run however
		"""
		
		GPIOPins = (6, 13, 19)
		direction= 23 # Direction (DIR) GPIO Pin
		step = 24 # Step GPIO Pin
		EN_pin = 25 # enable pin (LOW to enable)

		# Declare a instance of class pass GPIO pins numbers and the motor type
		self.mymotor = RpiMotorLib.A4988Nema(direction, step, GPIOPins, "DRV8825")
		GPIO.setup(EN_pin,GPIO.OUT) # set enable pin as output

		###########################
		# Actual motor control
		###########################

		GPIO.output(EN_pin,GPIO.LOW) # pull enable to lowto enable motor

	def pulseForward(self):
		print("Pulsing the motor forward...")
		steps = self.calculateSteps()
		print("Steps is: ", steps)
		self.mymotor.motor_go(False, # True=Clockwise - Back, False=Counter-Clockwise - Forward
						self.stepType, # Step type (Full,Half,1/4,1/8,1/16,1/32)
						steps, # number of steps
						self.stepDelay, # step delay [sec]
						False, # True = print verbose output 
						.05) # initial delay [sec]



	def cleanupGPIO(self):
		GPIO.cleanup() # clear GPIO allocations after run

		# cleanup is not absolutely necessary, especially if the we are not using 
		# GPIO pins for more than one action. Cleanup is necessary if this is done 
		# i.e. pin 16 used for input of signal and outputting signal 








