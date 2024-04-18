from ratBerryPi.resources.lickometer import Lickometer
import threading
from gpiozero import DigitalInputDevice
import board
import busio
from digitalio import Direction, Pull
from adafruit_mcp230xx.mcp23017 import MCP23017
import time
from datetime import datetime



class LickometerBus:
    GPIO_NAMES = [f"GPA{i}" for i in range(8)] + [f"GPB{i}" for i in range(8)]

    def __init__(self, bus_pin:int, on:threading.Event = None, lick_pins:dict = {}):

        self.on = on if on else threading.Event()
        self.addr = None
        self.lickometers = {}
        self.pin_map = [None for _ in range(16)]
        self.mcp = None

        for i,v in lick_pins.items(): self.add_lickometer(i, v)
        self.bus_pin = DigitalInputDevice(bus_pin, pull_up = True)
        self.bus_pin.when_activated = self.increment_licks

    def add_lickometer(self, name:str, pin:str):
        assert isinstance(pin, str), "invalid pin"
        pin_name = pin.split(":")
        _addr = int(pin_name[0], 16) if len(pin_name) == 2 else 32
        if self.addr:
            assert _addr == self.addr, "the specified pin is not on the same bus as other lickometers on this bus"
        else:
            self.addr = _addr
            i2c = busio.I2C(board.SCL, board.SDA)
            self.mcp = MCP23017(i2c, address = self.addr)
        pin_n = self.GPIO_NAMES.index(pin_name[-1])
        self.pin_map[pin_n] = name
        pin = self.mcp.get_pin(pin_n)
        pin.direction = Direction.INPUT
        self.lickometers[name] = Lickometer(name, self, pin)

        self.mcp.interrupt_enable = self.mcp.interrupt_enable | 2**pin_n
        self.mcp.interrupt_configuration = 0x0000 # configure interrupt to compare all enabled pins against DEFVAL
        self.mcp.io_control = 0x44  # configure interrupt as open drain
        self.mcp.default_value = 0x0000 # set DEFVAL to all pins being low    
        self.mcp.clear_ints()
        return self.lickometers[name]


    def increment_licks(self, x):
        for pin_flag in self.mcp.int_flag:
            self.lickometers[self.pin_map[pin_flag]].increment_licks(None)
            while self.lickometers[self.pin_map[pin_flag]].lickPin.value:
                time.sleep(0.001)
        self.mcp.clear_ints()