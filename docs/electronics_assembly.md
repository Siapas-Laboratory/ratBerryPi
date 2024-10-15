## Interface PCB
### Required Components
* Assembeld Interface PCB + additional components that could not be assembled by the PCB manufacturer
* DRV8825 stepper motor driver (x1)
* Raspberry Pi (≥4)
* Male to Male Audio Cable (optional)
* [Innomaker HIFI DAC Pro Hat](https://www.amazon.com/Raspberry-DAC-Pro-ES9038Q2M-Resolution/dp/B0B2DJZTSF) (optional)
* Female to Female jumper
* USB cable

### Assembly Steps
*Flashing Pump Code to the Pico*
1. Follow the steps detailed [here](https://randomnerdtutorials.com/programming-raspberry-pi-pico-w-arduino-ide/) to flash [pump control code](../pico/pump_control/pump_control.ino) to the pico.

*Seting up the PCB*
1. Solder any components not soldered by the PCB manufacturer. Below we shos the assembled pcb as a reference for where the components should be soldered (TODO: need 3d models for all components and retake the screenshot of the fusion model with names of components overlayed. do a similar thing for the module PCB)
2. Plug the stepper motor driver in the appropriate slot on the interface pcb being careful to match the pins correctly.
3. Plug the 12V supply into the board to power on the driver (the hat should *NOT* be plugged into the pi as yet).
4. Follow the steps outlined [here]() to set the trimpot on the driver to output 2A of current. When finished unplug the 12V supply.
5. Now we will attach the components to the pi. The pi should be turned off at this stage. If Audio is needed plug in the audio hat first followed by the interface pcb. Connect the audio hat to the interface pcb additionally by an audio cable (use the headphone jack of the audio hat). Use standoffs as needed.
6. Plug any valves in to their appropriate slots on the interface. Plug in the pump as well.
7. Use a jumper to connect the male header pins to the appropriate GPIO pins given your config.yaml and presets.yaml file. These pins are unfortunately not labeled on the board in v1 but we show the names below:
![alt text](ims/interface_pcb_pins.png)
8. Plug the Pico into the Raspberry Pi using a USB cable. 
9. Plug in the 12V supply again and power on the pi. 


## Module PCB
### Required Components


### Assembly Steps

*Setting up the PCB*
1. Follow the below diagram to solder all components to the PCB

*Setting the Lickometer Trimpot*
