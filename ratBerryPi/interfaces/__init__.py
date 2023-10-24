# Borrowed from https://julienharbulot.com/python-dynamical-import.html
from inspect import isclass
from pkgutil import iter_modules
from pathlib import Path
import os
from importlib import import_module
from ratBerryPi.interfaces.base import BaseInterface

# iterate through the modules in the current package
package_dir = Path(__file__).resolve().parent
for f in package_dir.glob("**/*.py"):
    if (f.stem != "__init__") and (f.stem[0]!="."):
        # import the module and iterate through its attributes
        module = import_module(f"{__name__}.{os.path.relpath(f, package_dir)[:-3].replace(os.path.sep, '.')}")

        for attribute_name in dir(module):
            attribute = getattr(module, attribute_name)

            if isclass(attribute) and (issubclass(attribute, BaseInterface) or issubclass(attribute, BaseException)):            
                # Add the class to this package's variables
                globals()[attribute_name] = attribute