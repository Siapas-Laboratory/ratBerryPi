import board
import busio
import digitalio
from adafruit_mcp230xx.mcp23017 import MCP23017

# Initialize the I2C bus:
i2c = busio.I2C(board.SCL, board.SDA)
mcp = MCP23017(i2c)  # MCP23017

def config_output(pin):
    """
    convenience function crerating creating
    an digitalio object for interfacing a digital
    output. pins can either be integers specifying
    a GPIO pin or a string specigying a pin on the
    GPIO port expander bonnet
    """
    if type(pin) == str: # the pin is on the expander bonnet
        pin = int(pin[-1]) + 8*(pin[-2].lower() == 'b')
        p = mcp.get_pin(pin)
    else:
        p = digitalio.DigitalInOut(getattr(board, f'D{pin}'))
    p.direction = digitalio.Direction.OUTPUT
    return p
      

class ResourceLocked(BaseException):
    def __init__(self, msg):
        self.message = msg
    def __str__(self):
        return self.message
