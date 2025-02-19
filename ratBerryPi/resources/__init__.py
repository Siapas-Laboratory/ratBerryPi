# Borrowed from https://julienharbulot.com/python-dynamical-import.html
from inspect import isclass
from pkgutil import iter_modules
from pathlib import Path
from importlib import import_module
from .base import BaseResource


# iterate through the modules in the current package
package_dir = Path(__file__).resolve().parent
for (_, module_name, _) in iter_modules([package_dir]):

    # import the module and iterate through its attributes
    module = import_module(f"{__name__}.{module_name}")
    for attribute_name in dir(module):
        attribute = getattr(module, attribute_name)

        if callable(attribute) or (isclass(attribute) and (issubclass(attribute, BaseResource) or issubclass(attribute, BaseException))):            
            # Add the class to this package's variables
            globals()[attribute_name] = attribute