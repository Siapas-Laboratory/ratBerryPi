# ratBerryPi
An extendable Raspberry Pi based device for controlling multiple muli-functional reward modules. The device uses the open source [Poseidon Syringe Pump](https://pachterlab.github.io/poseidon/) to supply fluid as reward to any of multiple reward ports via a luer manifold and an array of media isolation solenoid valves. The manifold is connected to a reservoir which the device can be programmed to intermittently draw fluid from. 

The modules themselves are each fitted with a lickometer, speaker and LED. Up to 8 such modules can be connected to the central interface via ethernet. While the system is optimized for the use of these modules, the code is flexible, such that users may design custom modules with additional or fewer components ("plugins") as needed (see Configuration).

For hardware/circuit schematics and build instructions see the hardware folder.

## Software Installation - (Raspberry Pi)
Follow these steps to setup a raspberry pi for use with ratBerryPi:

1. First install the [adafruit-blinka library](https://learn.adafruit.com/circuitpython-on-raspberrypi-linux/installing-circuitpython-on-raspberry-pi). This may require a reboot once completed. 
2. Run the following to install the module for interfacing with the GPIO expander bonnet: 
```
sudo pip3 install adafruit-circuitpython-mcp230xx
```
3. Run the followint to install some additional dependencies:
```
sudo apt-get install libportaudio0 libportaudio2 libportaudiocpp0 portaudio19-dev python3-pandas
sudo apt-get install python3-pyaudio
```
4. Clone this repository and navigate to it from terminal.
5. Build and install the repository with the following commands
```
python3 setup.py bdist_wheel sdist
pip3 install .
```
*NOTE: When setting up a new raspberry pi, make sure to set the default audio output interface to the headphone jack using the [raspi-config](https://www.raspberrypi.com/documentation/computers/configuration.html#changing-the-audio-output). You may not get any sound from the speakers otherwise.*

## Software Installation - (Client Device)
As detailed in the Usage section below, one mode of operation of this system is to configure the raspberry pi that is connected to the hardware to function as a server that clients may connect to in order to trigger rewards or cues. For this to work, the ratBerryPi python package must also be installed on the client device. To install ratBerryPi on a client device, simply follow steps 4 and 5 above.


## Usage
There are 2 main modes of operation for this platform. The Raspberry Pi can be configured as a server that clients on other machines may connect to in order to run commands as needed. Alternatively, one may write a program on the raspberry pi itself which creates an instance of the `RewardInterface` class defined in `reward.py` and invoke methods of this class to run a behavioral protocol. The help documentation for the `RewardInterface` class includes relevant information about it's exposed methods for this second use case. Here we will elaborate on the server-client mode of operation.

### Server-Client Mode
To start a server on the raspberry pi for  for clients to connect to, simply run the command `python -m ratBerryPi.server`. This will expose 2 ports on the raspberry pi for clients to connect to, one for running commands through the reward interface, and another for broadcasting information about the state of the device.  By default the former port will be port 5562 and the latter will be 5563, but this can be set as needed by passing the arguments `--port` and `--broadcast_port`. By design, only one client may connect to the non-broadcasting port at a time.

On a client device, users may connect to the server from a python terminal by first creating an instance of the `Client` class defined in `client.py`, then calling its `connect` method. For example:

```
from ratBerryPi.client import Client

host = '123.456.789' # raspberry pi ip address
port = 5562
broadcast_port = 5563

cl = Client(host, port, broadcast_port)
cl.connect()
```

Once connected, the 2 most important methods of this class are `run_command` and `get`. 

`run_command` provides an interface to run commands remotely through the `RewardInterface` class. It takes as input 2 positional arguments, the first of which is a string indicating the name of a method in the RewardInterface class to run. The second argument is a dictionary specifying keyword arguments for this function. 

`get` provides an interface to retrieve state information from the reward interface; it takes as input a dictionary specifying the request. This dictionary must have a field `prop` specifying the property to get. It should also specify one of the following entities which this property belongs to: `module`, `plugin`, or `pump`.  When specifying the a module, the user may optionally also specify a plugin on that module to query. When only specifying `plugin`, this should refer to a plugin that is not attached to a module. An example call to `get` may look like this:

```
req = {
   'module': 'module1',
   'plugin': 'LED',
   'prop': 'on'
}
cl.get(req)
```

where we are determining whether or not the LED attached to module1 is on. Another common example is the following:

```
req = {
   'pump': 'pump1'
   'prop': 'position'
}
cl.get(req)
```

where we are getting the current position of the pump relative to the end of the track.

For those interested, we have also created [this python package](https://github.com/nathanielnyema/pyBehavior) which provides a GUI for remotely controlling the ratBerryPi and exposes methods for defining behavioral protocols to run using the modules.

## Operating the Syringe and Manifold
For optimal performance, before triggering any rewards, all lines for reward delivery must be filled with the solution to be delivered to the reward ports. The key to doing this properly is make sure there are as few air bubbles in the lines as possible. We've optimized a procedure for automatically filling the lines which we strongly recommend users call before triggering any rewards. The procedure involves first priming all of the lines by sequentially filling all segments of the manifold leading up to the reward ports. It is important that this happens first because if we try to draw fluid from the reservoir without eliminating all air from the manifold leading up to the valves, we will introduce air bubbles that will be very difficult to eliminate. Once the lines are primed, we alternate between delivering fluid to the lines to fill them, and refilling the syringe with fluid from the reservoir.

While this all occurs automatically once calling the function, users should keep in mind that this process can only work if the syringe used for filling the lines has at least as much volume as the dead volume leading up to the valves in the manifold. For efficiency, it may even be in the user's best interest to use a fairly large syringe (about 30 mL) to fill the lines and switch to a more precise syringe for the experiment itself.

## Configuration (TODO: update this section)
This package includes a default configuration file which reserves GPIO pins and pins on the GPIO expander to control up to 8 of our custom modules. For users that would like to create custom reward modules you fill need to create a custom config file and provide it's path as an argument when creating a RewardInterface or starting the server. When creating this file, the key fields to be specified are `modules`, `pumps`, and `plugins`.  Under `pumps`, the user must specify names for all pumps that will be controlled by the interface. Further, under each pump's name, one must specify the following fields, which mostly reference the pinout for the DRV8825, the driver for stepper motor actuating the pump.

* `stepPin` - The pin on the raspberry pi connected to the STEP pin of the driver
* `stepType` - The type of microstepping to use when stepping the motor. Either Full, Half, 1/4, 1/8, or 1/16.
* `flushPin` - A pin on the raspberry pi connected to a button to be used to manually progress the pump forward
* `revPin` - A pin on the raspberry pi connected to a button to be used to manually progress the pump backwards
* `dirPin` -  The pin on the raspberry pi connected to the DIR pin of the driver
* `modePins` - A list of pins on the raspberry pi connected to the M0, M1 and M2 pins on the driver in that order.
* `syringeType` *(optional)* -The type of syringe that will be loaded on the pump by default. Current options include: BD1mL, BD5mL, BD10mL, BD30mL, BD50/60mL. Note, these options refer to keys in a dictionary called `syringeTypeDict` defined in the `Syringe` class in `pump.py`. Users may add additional syringes by adding new entries to this dictionary with the inner diameter of a given syringe and the maximum length the syringe can be withdrawn to when loaded on the pump (in cm).
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


 The only constraint in configuring reward modules is that each module must specify a single pump that it is attached to and, optionally, a pin for controlling the valve on the manifold which feeds the port. The pump need not be unique to each module, but the valves should be unique. Indeed, in the design detailed here, all modules share a pump. Similarly, modules may share plugins as needed. 