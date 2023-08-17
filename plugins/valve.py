from RPi import GPIO

class Valve:
    def __init__(self, valvePin, NC = True):
        self.valvePin = valvePin
        self.NC = NC
        GPIO.setup(self.valvePin,GPIO.OUT)
        GPIO.output(self.valvePin,GPIO.LOW)
        self.opened = not self.NC

    def open(self):
        if not self.opened:
            print(f'opening {self.valvePin}')
            if self.NC:
                GPIO.output(self.valvePin,GPIO.HIGH)
            else:
                GPIO.output(self.valvePin,GPIO.LOW)
            self.opened = True

    def close(self):
        if self.opened:
            print(f'closing {self.valvePin}')
            if self.NC:
                GPIO.output(self.valvePin,GPIO.LOW)
            else:
                GPIO.output(self.valvePin,GPIO.HIGH)
            self.opened = False
