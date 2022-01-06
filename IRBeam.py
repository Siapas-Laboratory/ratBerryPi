
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

GPIO.add_event_detect(BEAM_PIN, GPIO.BOTH, callback=break_beam_callback)
message = input("Press enter to quit\n\n")
GPIO.cleanup()
#myBeam = beam()


