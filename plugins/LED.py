import RPi.GPIO as GPIO


class LED:
    #TODO: need s function to flash the led for a specified amount of time
    def __init__(self, LEDPin):
        self.LEDPin = LEDPin
        GPIO.setup(self.LEDPin, GPIO.OUT)
        GPIO.output(self.LEDPin, GPIO.LOW)
    
    def on(self):
        GPIO.output(self.LEDPin, GPIO.HIGH)
    
    def off(self):
        GPIO.output(self.LEDPin, GPIO.LOW)