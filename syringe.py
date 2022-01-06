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

#import FakeRPi.GPIO as GPIO

# import RPi.GPIO as GPIO
# from RpiMotorLib import RpiMotorLib
import time
from time import sleep 

################################
# RPi and Motor Pre-allocations
################################
#
# define GPIO pins

#Note: do not know if should make this like an initialization function 
#that sets up the pins or if dont need to just need to call function 
#from file and things wont need to be set, or if just need to 
# initialize once and then can call pulse forward whenever


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


	def syringeCall(self): 

		"""
		Note to self: If we can just run this piece of code once and then never 
		have to call it again to make the motor run, then move this code into
		the initialization code above. 


		If the GPIO pins are set and will never move, then running 
		this kind of code that sets up the pins and everything for each object 
		i.e. speakers, lickometer, camera, etc. That way it can be flexible but 
		it is easily found and is code that can run on its own without the 
		need for a user to call it. 

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

	def calibration(self):
		print("Calibrating...")
		steps = self.calculateSteps(amount = 5, units = "microliters") #steps for 5 microliter 
		print("Steps is: ", steps) #should be 44! 
		for i in range(self.loopNumber):
			sleep(1)
			mymotortest.motor_go(False, # True=Clockwise - Back, False=Counter-Clockwise - Forward
							 stepType, # Step type (Full,Half,1/4,1/8,1/16,1/32)
							 steps, # number of steps
							 stepDelay, # step delay [sec]
							 False, # True = print verbose output 
							 .05) # initial delay [sec]
		print("Motor going back to initial place...")    
		for i in range(self.loopNumber):
			sleep(1)
			mymotortest.motor_go(True, # True=Clockwise - Back, False=Counter-Clockwise - Forward
						 stepType, # Step type (Full,Half,1/4,1/8,1/16,1/32)
						 steps, # number of steps
						 stepDelay, # step delay [sec]
						 False, # True = print verbose output 
						 .05) # initial delay [sec]


	def cleanupGPIO(self):
		GPIO.cleanup() # clear GPIO allocations after run

		# I am not too sure where this clean up code should go, indented or outside or
		# in file that calls the function? Going to leave in the 
		# function for now








