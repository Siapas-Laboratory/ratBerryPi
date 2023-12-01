import board
import busio
import digitalio
from adafruit_mcp230xx.mcp23017 import MCP23017

# Initialize the I2C bus:
i2c = busio.I2C(board.SCL, board.SDA)
mcps =  {32: MCP23017(i2c)}


def config_output(pin):
    """
    convenience function crerating creating
    an digitalio object for interfacing a digital
    output. pins can either be integers specifying
    a GPIO pin or a string specigying a pin on the
    GPIO port expander bonnet
    """
    if type(pin) == str: # the pin is on the expander bonnet
        pin = pin.split(':')
        if len(pin) == 2:
            addr = int(pin[0], 16)
            if addr not in mcps:
                mcps[addr] = MCP23017(i2c, address = addr)
        elif len(pin) == 1:
            addr = 32
        else:
            raise ValueError('invalid pin specified')
        pin = pin[-1]
        pin = int(pin[-1]) + 8*(pin[-2].lower() == 'b')
        p = mcps[addr].get_pin(pin)
    else:
        p = digitalio.DigitalInOut(getattr(board, f'D{pin}'))
    p.direction = digitalio.Direction.OUTPUT
    return p
