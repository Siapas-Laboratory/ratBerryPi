from RPi import GPIO
import board
import busio
import digitalio
from adafruit_mcp230xx.mcp23017 import MCP23017

# Initialize the I2C bus:
i2c = busio.I2C(board.SCL, board.SDA)
mcp = MCP23017(i2c)  # MCP23017

def config_output(pin):
    if type(pin) == str:
        pin = int(pin[-1]) + 8*(pin[-2].lower() == 'b')
        p = mcp.get_pin(pin)
    else:
        p = digitalio.DigitalInOut(getattr(board, f'D{pin}'))
    p.direction = digitalio.Direction.OUTPUT
    return p


        

    