# Desi_FallRotation-
Code + documentation of Desi's fall rotation in the Siapas Laboratory. Project entailed developing initial steps of creating a new training chamber using python, raspberry pi, stepper motor, speaker, and other related components / pieces. 

## IRBeam.py
simple piece of code that detects whether there is a break in the IR beams. There are two approaches included in the file, as noted in the comment - using the event detection function (versus the while loop approach) would be the best method to achieve flexibility in where to place event detection in the other files (especially main.py) 

## audio.py

generates sine wave based on certain parameter values:
* frequency (Hz)
* duration (ranges from 0.0 to <300 seconds)
* volume (ranges from 0.0 to 1.0) 
* sample rate (samples per second) 

outputs the sine wave through the audio port on the raspberry pi 

## calibration.py 

this is also written as a function in syringe.py - but it is included as its own file in the case the original code / user prompts used for calibration during the rotation is preferred. It goes through a for loop and outputs puleses of minimal amounts of water (5 microliters) for that amount of times. 


## syringe.py 

in reality this controls the movement of the stepper motor, and there are different 
values that are set to output the desired amount.

* units     microliters or milimeters 
* amount    integer value of amount of chosen units to output 
* syringeType   3 mL or 1 mL syringe 
* stepDelay     Would not recommend changing, but it is the delay between one movement of the motor to the next 
* stepType    "Full", "Half", "1/4", "1/16", "1/32". Automatically set to "Half".
* loopNumber    Number of loops during calibration 


## main.py
main interface file which references audio and syringe files. This is where the menu interface is built, and where calls to different functions are made. By building the other files using an object oriented programming approach, the main file can call functions on a syringe object or audio object. To run this file, navigate to its location in a terminal and simply run the file 

'''
python main.py 
'''
