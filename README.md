# ratBerryPi
A Raspberry Pi based system for controlling multiple muli-functional reward modules. Functionality is provided for interfacing with the device either locally on the Pi or remotely from a client device. The device uses the open source [Poseidon Syringe Pump](https://pachterlab.github.io/poseidon/) to supply fluid as reward to any of multiple reward ports via a luer manifold and an array of media isolation solenoid valves. The manifold is connected to a reservoir which the device can be programmed to intermittently draw fluid from. The modules themselves are each fitted with a lickometer, speaker and LED. Up to 8 such modules can be connected to the central interface via ethernet. While the system is optimized for the use of these modules, the code is flexible, such that users may design custom modules with additional or fewer components ("resources") as needed (see Configuration).


## Software Installation - (Raspberry Pi)
Clone this repository then follow these steps to setup a raspberry pi for use with ratBerryPi:

1. If you haven't already, install miniforge3 as described here

2. If you already have a conda environment you would like to use activate it. If not create one and activate it by running:

```
conda env create -n ratBerryPi
conda activate ratBerryPi
```

3. Run the following to configure the pi for use with the adafruit-blinka library (copied from [here](https://learn.adafruit.com/circuitpython-on-raspberrypi-linux/installing-circuitpython-on-raspberry-pi)):

```
cd ~
pip3 install --upgrade adafruit-python-shell
wget https://raw.githubusercontent.com/adafruit/Raspberry-Pi-Installer-Scripts/master/raspi-blinka.py
sudo -E env PATH=$PATH python3 raspi-blinka.py
```


4. After the reboot, navigate to this directory, re-activate the conda environment and run the following to finish the installation:

```
conda install portaudio pyqt
pip3 install .
```

*NOTE: When setting up a new raspberry pi, make sure to set the default audio output interface to the headphone jack using the [raspi-config](https://www.raspberrypi.com/documentation/computers/configuration.html#changing-the-audio-output). You may not get any sound from the speakers otherwise.*

## Software Installation - (Client Device)
As detailed in the Usage section below, one mode of operation of this system is to configure the raspberry pi that is connected to the hardware to function as a server that clients may connect to in order to trigger rewards or cues. For this to work, the ratBerryPi python package must also be installed on the client device. To install ratBerryPi on a client device, simply follow steps 4 and 5 above. If installing for use with [pyBehavior](https://github.com/nathanielnyema/pyBehavior), be sure to have the pyBehavior environment activated while performing these steps.

## Architecture
RatBerryPi consists of 3 layers of abstraction: the reward interface, reward modules and resources. The interface orchestrates use of all modules and resources. Resources are considered to be devices such as a syringe pump or solenoid valve which we may want to actuate and may be shared accross modules. Modules are collections or resources some of which may be unique to that module. Importantly, the module must have associated to it a valve which can be actuated to direct the flow of fluid to it. In the default use case, the interface has associated to it a set of pumps which several reward modules share. Each module has a valve, an led, a lickometer and a speaker associated to it.

**Technical Notes**
#TODO: add some info here about how the multi-speaker control is implemented in hardware and what this means for how the speakers are controlled and also the lickometer bus

## Usage
There are 2 main modes of operation for this platform. The Raspberry Pi can be configured as a server that clients on other machines may connect to in order to run commands through a specified interface. Alternatively, one may write a program on the raspberry pi itself which creates an instance of an interface class and invokes methods of this class to run a behavioral protocol. The help documentation for the RewardInterface class includes relevant information about it's exposed methods for this second use case. Here we will elaborate on the server-client mode of operation.

### Server-Client Mode
We provide a cli for creating either a server or a cli via the command `ratBerryPi` which can be called from the command line. To start a server on the raspberry pi, simply run the command `ratBerryPi server`. This will expose a port on the raspberry pi for clients to connect to for running commands through the reward interface and broadcasting information about the state of the device.  By default it will bind port 5562 but this can be set as needed by passing the arguments `--port`. If using an interface other than the reward interface. To start a client via the cli simply run the command `ratBerryPi client`. The default behavior of this method is to connect to a server hosted locally. If you would like to connect to a ratBerryPi server from a separate client device provide the `--host` argument.

Users may connect to the server programmatically by first creating an instance of the `Client` class defined in `client.py`. For example:

```
from ratBerryPi.client import Client

host = '123.456.789' # raspberry pi ip address
port = 5562

cl = Client(host, port)
```

Once you've created the client, the 2 most important methods of this class are `run_command` and `get`. 

`run_command` provides an interface to run commands remotely through the interface running on the server. It takes as input 2 positional arguments, the first of which is a string indicating the name of a method in the interface class to run. The second argument is a dictionary specifying keyword arguments for this function. 


`get` provides an interface to retrieve state information from the reward interface; it takes as input a string indicating the attribute of interface class you would like to get the value of. This string should be everything that would come after the period when directly accessing an instance of the interface class. for example, if we want the position of a pump named `pump1` when using the reward interface, the request would be `'pumps["pump1"].position'`.  


Both `run_command` and `get` further take as input an optional keyword argument `channel` which allows the user to specify the name of a 'channel' for communicating with the server. These channels are simply an abstraction for a connection to the server and allow users to isolate certain types of requests to avoid cross talk. For example, I may want to create an app using the reward interface where it would be useful to spawn a thread in the background to continuously monitor the position of the pump so I can print it for the user to see. It would be useful in this case to create a new channel specifically dedicated to these requests. Behind the scenes the server keeps these channels isolated by spawning separate threads for handling requests made on different channels. To create a new channel simply use the method of the client class `new_channel` which takes as input one positional argument which is the name of the new channel.


For those interested, [pyBehavior](https://github.com/nathanielnyema/pyBehavior) provides a GUI for remotely controlling the ratBerryPi and exposes methods for defining behavioral protocols to run using the modules.


## Practical Considerations when Operating the Syringe and Manifold
For optimal performance, before triggering any rewards, all lines for reward delivery must be filled with the solution to be delivered to the reward ports. The key to doing this properly is make sure there are as few air bubbles in the lines as possible. We've optimized a procedure for automatically filling the lines which we strongly recommend users call before triggering any rewards. The procedure involves first priming all of the lines by sequentially filling all segments of the manifold leading up to the reward ports. It is important that this happens first because if we try to draw fluid from the reservoir without eliminating all air from the manifold leading up to the valves, we will introduce air bubbles that will be very difficult to eliminate. Once the lines are primed, we alternate between delivering fluid to the lines to fill them, and refilling the syringe with fluid from the reservoir.

While this all occurs automatically once calling the function, users should keep in mind that this process can only work if the syringe used for filling the lines has at least as much volume as the dead volume leading up to the valves in the manifold. For efficiency, it may even be in the user's best interest to use a fairly large syringe (about 30 mL) to fill the lines and switch to a more precise syringe for the experiment itself.

## Configuration
This package includes a default configuration file which reserves GPIO pins and pins on the GPIO expander to control up to 8 of our custom modules. For users that would like to create custom reward modules you will need to define the module under the `ratBerryPi/interfaces/reward/modules` folder by sub-classing the BaseRewardModule class (see `ratBerryPi/interfaces/reward/modules/default.py` for an example). Importantly, the user must define a method `load_from_config` in the sub-class which should take as input a dictionary with configuration parameters for the module (such as pin mappings) and instantiate any resources the module needs as necessary. This dictionary will come from the `config.yaml` file where it is represented as the sub-fields of a given module listed under the `modules` section. As such, these sub-fields in the config file must be specified as needed for the configuration of the module in your `load_from_config` method. Some other required sub-fields for each module are as follows:

* `type` - the name of your custom reward module class
* `pump` - the name of the pump feeding into this reward module class
 * `valvePin`- a pin on the raspberry pi for controlling the valve on the manifold which routes reward to this module
 * `dead_volume` *(optional)* - the dead volume of the line leading up to the module in mL.

The other important fields of the config file are `pumps` and `plugins`.  Under `pumps`, the user must specify names for all pumps that will be controlled by the interface. Further, under each pump's name, one must specify the following fields, which mostly reference the pinout for the DRV8825, the driver for stepper motor actuating the pump.

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
 * `plugins` - an enumerated list of all plugins attached to this module. the keys should be general names for what the plugin is to the given module. Generally, this will might be the plugin type. For example, we may attach lickometer1 to module1 by specifying the `plugins` field of module1 as follows:

 ```
 plugins:
    lickometer1:
         type: Lickometer
         lickPin: 10
 ```


 The only constraint in configuring reward modules is that each module must specify a single pump that it is attached to and, optionally, a pin for controlling the valve on the manifold which feeds the port. The pump need not be unique to each module, but the valves should be unique. Indeed, in the design detailed here, all modules share a pump.


## Developer Notes
We encourage users to clone the repository and customize the code to their needs. To define a new resource sub-class the BaseResource class in the ratBerryPi/resources folder and define the class in a file in the same folder. Note, in the interest of thread safety, the BaseResource class when initialized has an attribute `lock` which is a re-entrant lock (see [here](https://docs.python.org/3/library/threading.html#rlock-objects) for details). We recommend developers to use this lock as a way to reserve resources in case multiple clients try to access it. To create a new module simply sub-class the BaseModule class under ratBerryPi/modules and define the class within a file you create in this same folder. Importantly this BaseModule class is an abstractbaseclass which expects the user to define a load_from_config method in the subclass which will configure the module instance using a config specified as a dict which is loaded from each module field within the config file. For an example see the default module. After making any changes you can reinstall the ratBerryPi by navigating to the root directory of the repo and running `pip3 install .`
