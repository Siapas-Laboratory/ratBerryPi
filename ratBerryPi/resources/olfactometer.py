from ratBerryPi.resources.base import BaseResource, ResourceLocked

class Olfactometer(BaseResource):
    def __init__(self, name):
        super(Olfactometer, self).__init__(name, None)
        pass

    def set_dilution(self):
        pass

    def set_flowrate(self):
        pass

    def prep_odor(self):
        pass

    def release_odor(self):
        pass