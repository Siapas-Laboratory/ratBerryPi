import numpy as np
from ratBerryPi.resources.base import BaseResource
from ratBerryPi.utils import config_output
import pyaudio as pa



class AudioInterface:
    def __init__(self, fs = 192_000):
        self.session = pa.PyAudio()
        devs = [self.session.get_device_info_by_index(i)['name'] 
                for i in range(self.session.get_device_count())]
        is_allo = ['Allo' in i for i in devs]
        self.out_index = int(np.where(is_allo)[0][0]) if any(is_allo) else None
        self.fs = fs
        self.stream = None
        self.speakers = {}

    def start(self):
        pass

    def add_speaker(self, name,  SDPin):
        self.speakers[name] = AudioInterface.Speaker(name, self, SDPin)
        return self.speakers[name]

    def play_tone(self, speakers, freq, dur, volume=1, force = True):
        if freq>=(self.fs/2):
            raise ValueError(f"the requested frequency is greater than the Nyquist frequency of interface ({self.fs/2:.2f} Hz)")
        if self.stream:
            if self.stream.is_active():
                if force:
                    self.stream.stop_stream()
                    for i in self.speakers:
                        self.speakers[i].disable()
                else:
                    return
            self.stream.close()
        for i in speakers:
            self.speakers[i].enable()          
            
        n_samples = int(self.fs * dur)
        restframes = n_samples % self.fs
        t = np.arange(n_samples)/self.fs
        self.samples = volume * np.sin(2* np.pi * freq * t)
        self.samples = np.concatenate((self.samples, np.zeros(restframes))).astype(np.float32).tobytes()


        def callback(in_data, frame_count, time_info, status):
            if len(self.samples)>0:
                nbytes = int(frame_count * 4)
                data = self.samples[:nbytes]
                if len(self.samples) > nbytes:         
                    self.samples = self.samples[nbytes:]
                    return (data, pa.paContinue)
                else:
                    for i in self.speakers:
                        self.speakers[i].disable()
                    return (None, pa.paComplete)
            else:
                for i in self.SDPins:
                    self.SDPins[i].value = False
                return (None, pa.paComplete)

        self.stream = self.session.open(format = pa.paFloat32,
                                      channels = 1,
                                      rate = self.fs,
                                      output = True,
                                      output_device_index=self.out_index,
                                      stream_callback = callback)
        self.stream.start_stream()

    def __del__(self):
        if self.stream is not None:
            self.stream.close()
        self.session.terminate()

    class Speaker(BaseResource):
        def __init__(self, name, parent, SDPin):
            super(AudioInterface.Speaker, self).__init__(name, parent)
            self.SDPin = config_output(SDPin)
            self.SDPin.value = False

        @property
        def enabled(self):
            return self.SDPin.value

        def enable(self):
            self.SDPin.value = True

        def disable(self):
            self.SDPin.value = False

        def play_tone(self, freq, dur, volume=1, force = True):
            self.parent.play_tone([self.name], freq, dur, volume, force)

