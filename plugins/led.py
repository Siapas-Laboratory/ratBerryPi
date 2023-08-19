import RPi.GPIO as GPIO


class LED:
    #TODO: need s function to flash the led for a specified amount of time
    def __init__(self, name, LEDPin):
        self.name = name
        self.LEDPin = LEDPin
        GPIO.setup(self.LEDPin, GPIO.OUT)
        GPIO.output(self.LEDPin, GPIO.LOW)
        self.on = False
    
    def turn_on(self):
        GPIO.output(self.LEDPin, GPIO.HIGH)
        self.on = True
    
    def turn_off(self):
        GPIO.output(self.LEDPin, GPIO.LOW)
        self.on = False