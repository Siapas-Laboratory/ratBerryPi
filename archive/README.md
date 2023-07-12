# Desi_FallRotation-
Code + documentation of Desi's fall rotation in the Siapas Laboratory. Project entailed developing initial steps of creating a new training chamber using python, raspberry pi, stepper motor, speaker, and other related components / pieces. 

## IRBeam.py
simple piece of code that detects whether there is a break in the IR beams. There are two approaches included in the file, as noted in the comment - using the event detection function (versus the while loop approach) would be the best method to achieve flexibility in where to place event detection in the other files (especially main.py) 

### functions
def break_beam_callback(channel):
* channel = meaningless parameter, it is there so that the function can be called currently from GPIO.add_event_detect


## audio.py

generates sine wave based on certain parameter values:
* frequency (Hz)
* duration (ranges from 0.0 to <300 seconds)
* volume (ranges from 0.0 to 1.0) 
* sample rate (samples per second) 

outputs the sine wave through the audio port on the raspberry pi 

### functions 

def sine_tone(self, frequency, duration, volume=1, sample_rate=22050)
* frequency = frequency of sound output in Hz 
* duration = length of the audio 
* volume = volume of sound output, automatically set to 100% volume. 
* sample rate = samples per second, automatically set to 22050



## syringe.py 

in reality this controls the movement of the stepper motor, and there are different 
values that are set to output the desired amount.

* units     microliters or milimeters 
* amount    integer value of amount of chosen units to output 
* syringeType   3 mL or 1 mL syringe 
* stepDelay     Would not recommend changing, but it is the delay between one movement of the motor to the next 
* stepType    "Full", "Half", "1/4", "1/16", "1/32". Automatically set to "Half".
* loopNumber    Number of loops during calibration 

### functions 

def calculateSteps(self)
calculates steps based on amount, units, syringeType, stepType 

def syringeGPIOInit(self)
intializes GPIO pins of the syringe amd sets it up 

def pulseForward(self)
pulses the motor forward by just the number of steps 

def cleanupGPIO(self)
resets the GPIO pins 


## main.py
main interface file which references audio and syringe files. This is where the menu interface is built, and where calls to different functions are made. By building the other files using an object oriented programming approach, the main file can call functions on a syringe object or audio object. To run this file, navigate to its location in a terminal and simply run the file 


python main.py 

### functions 

def highTone()
plays sound output at frequency set for the high tone 

def lowTone()
plays sound output at frequency set for the low tone 

def settingsMode()
enters setting mode to adjust different values set up for the audio or syringe.
this is not as well developed. 

def experimentMode()
enters experiment mode where user has option to pulse syringe, play high tone and low tone, or enter settings mode 

