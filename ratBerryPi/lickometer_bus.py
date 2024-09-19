from ratBerryPi.resources.lickometer import Lickometer
import threading
from gpiozero import DigitalInputDevice
import board
import busio
from digitalio import Direction, Pull
from adafruit_mcp230xx.mcp23017 import MCP23017
import time
from datetime import datetime
from ratBerryPi.utils import i2c, mcps
from typing import Dict


class LickometerBus:
    """
    An interface for interacting with a set of lickometers all hosted on the 
    same MCP23017 i2c interface chip. 


    ...

    Attributes:
        on (threading.Event):
            threading Event for synchronizing lickometer threads with
            interface starting and stopping
        lickometers (Dict[str, Lickometer]):
            dictionary mapping lickometer names to the corresponding
            instances of the Lickometer class

    """
    GPIO_NAMES = [f"GPA{i}" for i in range(8)] + [f"GPB{i}" for i in range(8)]

    def __init__(self, bus_pin:int, on:threading.Event = None, lick_pins:dict = {}):
        """
        Args:
            bus_pin:
                GPIO pin designated to read the hardware interrupts 
                triggered by the MCP23017. rising edges detected on
                this pin will trigger the bus to poll the MCP23017
                for which lickometer triggered the interrupt if any
                and increment the lick count on the appropriate lickometer
                as needed
            on:
                threading Event for synchronizing lickometer threads with
                interface starting and stopping
            lick_pins:
                dictionary mapping lickometer names to GPIO pins
                they should be associated with. if specified
                all lickometers will be added to the bus on instantiation
        """

        self.on = on if on else threading.Event()
        self._addr = None
        self.lickometers = {}
        self._pin_map = [None for _ in range(16)]
        self._mcp = None

        for i,v in lick_pins.items(): self.add_lickometer(i, v)
        self.bus_pin = DigitalInputDevice(bus_pin, pull_up = False)
        self.bus_pin.when_activated = self._increment_licks

    def add_lickometer(self, name: str, pin: str) -> Lickometer:
        """
        add a lickometer to the bus

        Args:
            name:
                name of the lickometer to add
            pin:
                name of the GPIO pin to monitor for this lickometer
        Returns:
            lickometer: 
                a reference to the added lickometer
                which may also be accessed at self.lickometers[name]
        """
        global mcps
        global i2c
        assert isinstance(pin, str), "invalid pin"
        pin_name = pin.split(":")
        _addr = int(pin_name[0], 16) if len(pin_name) == 2 else 32
        if self._addr:
            assert _addr == self._addr, "the specified pin is not on the same bus as other lickometers on this bus"
        else:
            self._addr = _addr
            if self._addr not in mcps:
                mcps[self._addr] = MCP23017(i2c, address = addr)
            self._mcp = mcps[self._addr]
            self._mcp.clear_ints()
        pin_n = self.GPIO_NAMES.index(pin_name[-1])
        self._pin_map[pin_n] = name
        pin = self._mcp.get_pin(pin_n)
        pin.direction = Direction.INPUT
        self.lickometers[name] = Lickometer(name, self, pin)

        self._mcp.interrupt_enable = self._mcp.interrupt_enable | 2**pin_n
        self._mcp.interrupt_configuration = 0x0000 # configure interrupt to occur on any change
        # self._mcp.interrupt_configuration = 0xFFFF # configure interrupt to compare all enabled pins against DEFVAL
        self._mcp.io_control = 0b01000010  # configure interrupt as active-high
        # self._mcp.default_value = 0x0000 # set DEFVAL to all pins being low    
        self._mcp.clear_ints()
        return self.lickometers[name]


    def _increment_licks(self, x) -> None:
        """
        callback function that is called whenever an interrupt
        is detected. checks if a rising edge caused the interrupt
        and increments licks on the associated lickemeter if so
        """
        for pin_flag in self._mcp.int_flag:
            if self.lickometers[self._pin_map[pin_flag]].lickPin.value:
                self.lickometers[self._pin_map[pin_flag]].increment_licks(None)
        self._mcp.clear_ints()