# RatBerryPi
An extendable Raspberry Pi based device/platform for controlling multiple muli-functional reward modules. The device uses a modified version of the open source [Poseidon Syringe Pump](https://pachterlab.github.io/poseidon/) to supply fluid as reward to any of multiple reward ports via a luer manifold and an array of media isolation solenoid valves. The manifold is connected to a reservoir which the device can be programmed to intermittently draw fluid from. 

In the design detailed [here](), the modules themselves are each fitted with a lickometer, speaker and LED. The code, however, is flexible, such that users may design custom modules with additional or fewer components ("plugins") as needed (see Configuration).


## Software Installation - (Raspberry Pi)
Follow these steps to setup a raspberry pi for use with ratBerryPi:

1. First install the [adafruit-blinka library](https://learn.adafruit.com/circuitpython-on-raspberrypi-linux/installing-circuitpython-on-raspberry-pi). This may require a reboot at one point. 
2. Install some necessary pip installable dependencies. 
```
sudo pip3 install adafruit-circuitpython-mcp230xx
```
3. Install some more stuff that doesn't work well on linux when installed through pip.
```
sudo apt-get install libportaudio0 libportaudio2 libportaudiocpp0 portaudio19-dev python3-pandas
sudo apt-get install python3-pyaudio
```
4. Clone this repository and navigate to it from terminal.
5. Build and install the repository with the following commands
```
python3 setup.py bdist_wheel sdist
pip3 install .

*NOTE: When setting up a new raspberrypi, make sure to set the default audio output interface to the headphone jack using the raspi-config. You may not get any sound from the speakers otherwise.*
```
## Software Installation - (Client Device)
Follow steps 4 and 5 above.


## Configuration (TODO: update this section)
Before using the system, a `config.yaml` file must be created. This file is parsed to setup the pins on the raspberry pi. The provided `config.yaml` file contains pin definitions for the build detailed [here](). When configuring a custom setup, the key fields to be specified in this file are `PORT`, `BROADCAST_PORT`, `modules`, `pumps`, and `plugins`. `PORT` and `BROADCAST_PORT` are mainly needed for the Server-Client mode of operation (see Usage). Under `pumps`, the user must specify names for all pumps that will be controlled by the interface. Further, under each pump's name, one must specify the following fields, which mostly reference the pinout for the DRV8825, the driver for stepper motor actuating the pump.

* `stepPin` - The pin on the raspberry pi connected to the STEP pin of the driver
* `stepType` - The type of microstepping to use when stepping the motor. Either Full, Half, 1/4, 1/8, or 1/16.
* `flushPin` - A pin on the raspberry pi connected to a button to be used to manually progress the pump forward
* `revPin` - A pin on the raspberry pi connected to a button to be used to manually progress the pump backwards
* `dirPin` -  The pin on the raspberry pi connected to the DIR pin of the driver
* `GPIOPins` - A list of pins on the raspberry pi connected to the M0, M1 and M2 pins on the driver in that order.
* `defaultSyringeType` *(optional)* -The type of syringe that will be loaded on the pump by default. Current options include: BD1mL, BD5mL, BD10mL, BD30mL, BD50/60mL. Note, these options refer to keys in a dictionary called `syringeTypeDict` defined in the `Syringe` class in `pump.py`. Users may add additional syringes by adding new entries to this dictionary with the inner diameter of a given syringe and the maximum length the syringe can be withdrawn to when loaded on the pump (in cm).
* `fillValvePin` *(optional)* - A pin on the raspberry pi to control a valve attached to reservoir. This valve, if specified, will be used to allow fluid to be drawn into the syringe from the reservoir

*Pinout for the driver:*

![DRV8825 pinout](https://a.pololu-files.com/picture/0J4232.600.png?f2f6269e0a80c41f0a5147915106aa55)


Under `plugins` the user should specify unique names for each individual plugin used in the device. Under these names the user should further indicate any relevant arguments for specifying the plugin. All plugins should specify the argument `type`. See the provided config file for arguments required of already implemented plugins. When defining a new plugin be sure to create a file with a class definition for an object to control the plugin. Furthermore, be sure to implement logic for creating and instance of this class in the init function for `RewardInterface` in `reward.py` when parsing the config file. 

 Finally, under `modules`, the user should specify names for the modules that will be included on the interface. Under each name, the user must then indicate the following

 * `pump` - the name of the pump feeding into this reward module
 * `valvePin` *(optional)* - a pin on the raspberry pi for controlling the valve on the manifold which routes reward to this module
 * `plugins` - an enumerated list of all plugins attached to this module. the keys should be general names for what the plugin is to the given module. Generally, this will might be the plugin type. For example, we may attach lickometer1 to module1 by specifying the `plugins`` field of module1 as follows:

 ```
 plugins:
    lickometer: lickometer1
 ```


 The only constraint in configuring reward modules is that each module must specify a single pump that it is attached to and, optionally, a pin for controlling the valve on the manifold which feeds the port. The pump need not be unique to each module, but the valves should be unique. Indeed, in the design detailed here, all modules share a pump. Similarly, modules may share plugins as needed. If plugins are

## Usage
There are 2 main modes of operation for this platform. The Raspberry Pi can be configured as a server that clients on other machines may connect to in order to run commands as needed. Alternatively, one may write a program which creates an instance of the `RewardInterface` class defined in `reward.py` and invoke methods of this class to run a behavioral protocol. The help documentation for the `RewardInterface` class includes relevant information about it's exposed methods for this second use case. Here we will elaborate on the server-client mode of operation.

### Server-Client Setup
...


## Operating the Syringe and Manifold
For optimal performance, before using the device, all lines must be filled with the solution to be delivered to the reward ports. **The key here is making sure there are no air bubbles or at least as few as possible.** The following steps detail a fairly reliable procedure for accomplishing this

1. Start with all outlets to the reward ports blocked off on the manifold (as shown below; TODO: need a picture here). Fill the reservoir with the reward solution.

2. Attach a syringe with the piston all the way down (i.e. completely empty) to the inlet port  and manually fill the syringe while pressing the button to open the fill valve. Make sure there are no air bubbles in the manifold.

3. Remove the syringe and empty it’s contents 

4. Refill the syringe manually from the reservoir

5. Make sure there are no air bubbles in the syringe and reattach to the inlet port. When attaching, fill the luer connector with water from the syringe so that it is overflowing before fastening. This will help to prevent air bubbles from forming.

6. Open back up the ports on the manifold that go to the reward modules (as shown below; TODO: need a picture here).

7. If you have not already done so, start up the server on the raspberry pi and connect a client. Use the ‘fill_lines’ command to fill all of the lines with water. This will sequentially open the valves for the reward modules and inject a specified amount of water. The amount should be at least as much as the dead volume in the line but no more than the syringe volume. Note, sequential filling is important here because if we open all valves to flush all at once, the valves will not  fill evenly and we may end up with air bubbles.


Default ethernet port config:

```
port0:
  LEDPin: GPA0
  lickPin: 9
  SDPin: 10
  valvePin: GPA1

port1:
  LEDPin:  GPA2
  lickPin: 11
  SDPin: 12
  valvePin: GPA3

port2:
  LEDPin:  GPA4
  lickPin: 13
  SDPin: 14
  valvePin: GPA5

port3:
  LEDPin:  GPA6
  lickPin: 15
  SDPin: 16
  valvePin:  GPA7

port4:
  LEDPin: GPB0
  lickPin: 17
  SDPin: 18
  valvePin: GPB1

port5:
  LEDPin: GPB2
  lickPin: 19
  SDPin: 20
  valvePin: GPB3

port6:
  LEDPin: GPB4
  lickPin: 21
  SDPin: 22
  valvePin: GPB5

port7:
  LEDPin: GPB6
  lickPin: 23
  SDPin: 24
  valvePin: GPB7

```