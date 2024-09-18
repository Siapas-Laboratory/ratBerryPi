import numpy as np
from ratBerryPi.resources.base import BaseResource
from ratBerryPi.utils import config_output
import pyaudio as pa
import typing


class AudioInterface:

    # list of supported sampling rates in Hz
    # NOTE: at least on a pi 4, 88.2 kHz and up produces choppy
    # inconsistent output 
    SUPPORTED_FS = [44_100, 48_000, 88_200, 96_000, 192_000] 

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


    def __init__(self, fs = 48_000):

        self.session = pa.PyAudio()a
        self.fs = fs
        self.stream = None
        self.speakers = {}

        # use the output associated to the allo-katana DAC if available
        devs = [self.session.get_device_info_by_index(i)['name'] 
                for i in range(self.session.get_device_count())]
        is_allo = ['Allo' in i for i in devs]
        self.out_index = int(np.where(is_allo)[0][0]) if any(is_allo) else None

    @property
    def fs(self):
        return self._fs

    @fs.setter
    def fs(self, fs):
        assert fs in self.SUPPORTED_FS, f"{fs} is not a supported sampling rate. Supported sampling rates are as follows: {self.SUPPORTED_FS}"
        self._fs = fs

    def add_speaker(self, name:str,  SDPin:typing.Union[str, int]) -> Speaker:
        """
        add a speaker to the interface with the specified
        name and SDPin

        Args: 
            name: str
                name to assign the speaker
            SDPin: typing.Union[str, int]
                pin to toggle in order to mute this speaker.
                the convention is such that when this pin is low
                the speaker is muted. when high the speaker is enabled
        Returns:
            speaker: AudioInterface.Speaker
                reference to the speaker added to the interface
        """
        self.speakers[name] = AudioInterface.Speaker(name, self, SDPin)
        return self.speakers[name]

    def play(self, signal:np.ndarray, speakers:list, fs:float=None, force:bool = True) -> None:
        """
        play some arbitrary signal on the specified speakers

        Args:
            signal: np.ndarray
                1D array of the signal to play on the speakers
            speakers: list
                list of names of speakers to play the tone on
            fs: float
                sampling rate of the provided signal
                if specified the signal will be resampled to self.fs
                otherwise the signal will be assumed to have sampling rate
                self.fs
            force: bool
                flag indicating to stop any running streams to play
                this sound
        """

        assert isinstance(signal, np.ndarray), "signal must be a 1D numpy array"
        assert signal.ndim == 1, "signal must be a 1D numpy array"
        # if force is true stop any running streams
        if self.stream:
            if self.stream.is_active():
                if force:
                    self.stream.stop_stream()
                    # disable all speakers
                    for i in self.speakers:
                        self.speakers[i].disable()
                else:
                    return
            self.stream.close()

        # enable specified speakers
        for i in speakers:
            self.speakers[i].enable()

        # resample signal from specified sampling rate to the interface sampling rate
        if fs is not None:
            raise NotImplemented()
        # pad the signal such that the number of samples is an even multiple of the sample rate
        restframes = signal.size % self.fs
        signal = np.concatenate((signal, np.zeros(restframes))).astype(np.float32)
        self.samples = np.concatenate((signal, np.zeros(restframes))).astype(np.float32).tobytes()

        def callback(in_data, frame_count, time_info, status):
            """
            callback for audio stream
            pulls frame_count * 4  bytes (4 bytes per float32 sample) 
            of data from the queued samples and pushes them to the speaker
            """
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

        # create and start the audio stream
        self.stream = self.session.open(format = pa.paFloat32,
                                      channels = 1,
                                      rate = self.fs,
                                      output = True,
                                      output_device_index=self.out_index,
                                      stream_callback = callback)
        self.stream.start_stream()

    def play_tone(self, speakers:list, freq:float, dur:float, volume:float=1, force:bool = True) -> None:
        """
        play a sine tone of a specified frequency, duration and volume
        on the specified speakers

        Args:
            speakers: list
                list of names of speakers to play the tone on
            freq: float
                desired frequency of the tone. this must not exceed the
                Nyquist frequency for the interface (self.fs/2)
            dur: float
                desired duration of the tone
            volume: float
                value between 0 and 1 indicating the fraction
                of max volume to play the sound at
            force: bool
                flag indicating to stop any running streams to play
                this sound
        """
        if freq>=(self.fs/2):
            raise ValueError(f"the requested frequency is greater than the Nyquist frequency of interface ({self.fs/2:.2f} Hz)")  
        n_samples = int(self.fs * dur)
        t = np.arange(n_samples)/self.fs
        samples = volume * np.sin(2* np.pi * freq * t)
        self.play(samples, speakers, force=force)

    def __del__(self):
        if self.stream is not None:
            self.stream.close()
        self.session.terminate()