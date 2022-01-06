#######################################
#
#code influenced by https://simonprickett.dev/using-a-break-beam-sensor-with-python-and-raspberry-pi/
#
# Desiderio Ascencio 
#######################################


import RPi.GPIO as GPIO

BEAM_PIN = 26

GPIO.setmode(GPIO.BCM)
GPIO.setup(BEAM_PIN, GPIO.IN)

# NOTE: This code below can be used 
# to detect events. This stays in the loop 
# though and so it is not exactly what is needed 
# but it does work if want to test the IR beams 

# try:
#     while True:
#         if GPIO.input(BEAM_PIN):
#             print("Event Detected!")
#         else:
#             print("Nothing...")
# except KeyboardInterrupt:
#     GPIO.cleanup()

# code below is best bet to make the event detection 
# flexible enough to be used in the main file 
# or any other files 


def break_beam_callback(channel):
    if GPIO.input(BEAM_PIN):
        print("beam unbroken")
    else:
        print("beam broken")


GPIO.add_event_detect(BEAM_PIN, GPIO.BOTH, callback=break_beam_callback)
message = input("Press enter to quit\n\n")
GPIO.cleanup()
#myBeam = beam()


