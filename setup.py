from setuptools import setup, find_packages

setup(
    name = "ratBerryPi",
    version = '0.0.0',
    author = "Nathaniel Nyema",
    author_email = "nnyema@caltech.edu",
    description = "A Raspberry Pi based system for cue presentation and fluid reward delivery in rodent behavioral experiments.", 
    packages = find_packages(),
    entry_points = {
        'console_scripts': [
            'ratBerryPi = ratBerryPi.cli:main'
        ]
    },
    package_data = {"": ["*.yaml"]},
    extras_require = {
        'pi':[
            'scipy',
            'pyyaml',
            'numpy',
            'gpiozero',
            'rpi-lgpio',
            'lgpio',
            'pygame',
            'adafruit-blinka',
            'adafruit-circuitpython-mcp230xx'
        ]
    }
)
