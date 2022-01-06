########################################
#
# This code is influenced by 
# https://makersportal.com/blog/raspberry-pi-stepper-motor-control-with-nema-17
# https://www.rototron.info/raspberry-pi-stepper-motor-tutorial/
#
# Desiderio Ascencio 
#######################################
import os
import time
from audio import * 
from syringe import *
import math 

# creating speaker object 
mySpeaker = audioObject()

#fucntions 

#play high tone function 
def highTone():
    mySpeaker.sine_tone( #from audio.py
    # see http://www.phy.mtu.edu/~suits/notefreqs.html
    frequency=mySpeaker.highFrequency, # Hz, waves per second A4
    duration=1, # seconds to play sound
    volume=.9, # 0..1 how loud it is
    # see http://en.wikipedia.org/wiki/Bit_rate#Audio
    sample_rate=22050 # number of samples per second
    )

#play low tone function 
def lowTone():
    mySpeaker.sine_tone( #from audio.py
    # see http://www.phy.mtu.edu/~suits/notefreqs.html
    frequency=mySpeaker.lowFrequency, # Hz, waves per second A4
    duration=1, # seconds to play sound
    volume=.9, # 0..1 how loud it is
    # see http://en.wikipedia.org/wiki/Bit_rate#Audio
    sample_rate=22050 # number of samples per second
    )

# SETTINGS

# def audioSettings():
#     print("Audio Settings")
#     print(mySpeaker.lowFrequency)
#     print(mySpeaker.highFrequency)

# def syringeSettings():
#     print("Syringe Settings")

def settingsMode(): #have to pass in a syringe object too 
    print("\n\033[1;33;40mENTERING SETTINGS MODE ...")

    settingsOption = int(input("\n\033[1;37;40m\n1)audio settings\n2)syringe settings\n3)back to main menu\nchoose option: \033[1;37;40m"))
    
    while settingsOption not in [1, 2, 3]:
        settingsOption = int(input("\n\033[1;37;40m\nYou did not choose an availiable option, please try again\n1)audio settings\n2)syringe settings\n3)back to main menu\nchoose option: \033[1;37;40m"))
    
    if settingsOption == 1:
        audioSettings()
    elif settingsOption == 2:
        syringeSettings() #pass in syringe object 
    else: #settingsOption == 3 
        mainMenu()


#below is the code that I harcoded 
#to run the pseudo mouse experiments
#with the box.
def runExperiment():
    BEAM_PIN = 26

    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BEAM_PIN, GPIO.IN)
    
    initTime = time.time()
    waterCounter = 0
    hits = 0
    misses = 0 
    
    for i in range(143):
        print("\n\n------- TRIAL {} -------\n\n".format(i))
        if time.time() - initTime > 60:
            print("TIME ELAPSED: {}".format(time.time() - initTime)) #print in MM:SS format 
        else:
            print("TIME ELAPSED: {}".format(time.time() - initTime))
            
        print("TONE")
        highTone()
        print("DELAY")
        time.sleep(2)
        # code below is just as I imagine, subject to change w how lickometer is put together
        
        print("REWARD PERIOD")
        timedReward = 3 
        startTime = time.time()
        rewardState = True 
        while (time.time() - startTime) < timedReward:
            if GPIO.input(BEAM_PIN) and rewardState == True:
                print("beam broken!")
                mySyringe.pulseForward()
                mySyringe.waterCounter += 1 
                rewardState = False
                hits += 1 
            else:
                pass
        rewardState = False
        print("INTERVAL 20 secs")
        print("Water count: {}".format(mySyringe.waterCounter))
        print("Water displaced: {} microliters".format(mySyringe.waterCounter * 6 )) #harcoded - make the 6 generalized to the output 
        print("Hits: {0} Misses: {1}".format(hits, misses))
        time.sleep(20)
    

# EXPERIMENT MODE 
#gives user ability to run an experiment, or manipulate different components such as playing tones or pulsing the syringe 
def experimentMode():
    print("\n\033[1;33;40mSTARTING EXPERIMENT MODE ...")

    expOption = 1 
    while expOption in [1, 2, 3]:
        expOption = int(input("\033[1;37;40m1)high tone\n2)low tone\n3)activate syringe\n4)run experiment\n5)settings\n6)exit\nchoose option: "))
        
        while expOption not in [1,2,3,4,5]:
                expOption = int(input("\n\033[1;37;40mYou did not choose an available option, please try again\n1)high tone\n2)low tone\n3)activate syringe\n4)run experiment\n5)settings\n6)exit\nchoose option: \033[1;37;40m"))

        if expOption == 1:
            highTone()
        elif expOption == 2:
            lowTone()
        elif expOption == 3: 
            mySyringe.pulseForward()
        elif expOption == 4:
            runExperiment()
        elif expOption == 5: 
            settingsMode()
        else: #option 5 was chosen
            print("\n\033[1;33;40mEXITING ...")
            exit



# CHOOSING MODE 
def mainMenu():
    print("\n\033[1;32;40mCHOOSE MODE")
    mode = int(input("\033[1;37;40m1)callibration\n2)experiment\n3)settings\nChoose an option: "))

    while mode not in [1, 2, 3]:
        mode = int(input("\033[1;37;40mYou did not choose an available option, please try again.\n1)callibration\n2)experiment\n3)settings\nChoose an option: "))
    else:
        if mode == 1: #callibration mode 
            print("callibration mode")
            callibrationMode()
        elif mode == 2: #experiment mode 
            print("experiment mode")
            experimentMode()
        else:
            settingsMode()



# WELCOME MESSAGE 
print("\033[1;33;40mWELCOME TO BOX INTERFACE!\n")

# ASKING USER FOR DESIRED OUTPUT 

"""
Note: Could rewrite this using argparse so it is cleaner
"""
print("\033[1;32;40m CHOOSE UNITS")
unitsOption = int(input("\033[1;37;40m1)milliliters mL\n2)microliters uL\nChoose an option: "))

while unitsOption not in [1, 2]:
    print("\n\n\033[1;32;40m You did not choose an availiable option, please try again.")
    unitsOption = int(input("\033[1;37;40m1)milliliters mL\n2)microliters uL\nChoose an option: "))

if unitsOption == 1:
    units = "milliliters"
else:
    units = "microliters"

amount = int(input("\033[1;37;40mEnter amount of {0} to output: \033[1;37;40m".format(units)))

# SYRINGE 

syringeOption = int(input("\033[1;32;40mCHOOSE SYRINGE TYPE\033[1;37;40m\n1)1mL\n2)3mL\nChoose an option: "))

while syringeOption not in [1, 2]:
    print("\n\n\033[1;32;40m You did not choose an availiable option, please try again.")
    syringeOption = int(input("\033[1;32;40mCHOOSE SYRINGE TYPE\n\033[1;37;40m1)1mL\n2)B3mL\nChoose an option: "))

if syringeOption == 1:
    syringeType = "1mL"
else:
    syringeType = "3mL"

mySyringe = syringe(amount, syringeType)
mySyringe.syringeGPIOInit()


mainMenu()




