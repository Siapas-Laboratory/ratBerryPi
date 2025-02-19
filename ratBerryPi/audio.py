import numpy as np
from scipy.interpolate import interp1d
from ratBerryPi.resources.base import BaseResource
from ratBerryPi.utils import config_output
import pygame
from typing import Union, Dict
import threading
import time
import logging


logger = logging.getLogger(__name__)

class AudioInterface:

    """
    an interface for playing audio on the raspberry pi
    
    ...
    
    Attributes:
        fs (float):
            sampling rate of the interface
        speakers (Dict[str, Speaker]):
            dictionary mapping speaker names to their
            associated instances of the AudioInterface.Speaker
            class
        out_index (int):
            index of the audio output device to use when playing
            audio. if None the system default is used


    """

    # list of supported sampling rates in Hz
    # NOTE: at least on a pi 4, 88.2 kHz and up produces choppy
    # inconsistent output 
    SUPPORTED_FS = [44_100, 48_000, 88_200, 96_000, 192_000] 

    class Speaker(BaseResource):
        """
        a speaker that an audio interface may play sound through
        """
        def __init__(self, name: str, parent, SDPin: Union[str, int]):
            super(AudioInterface.Speaker, self).__init__(name, parent)
            self.SDPin = config_output(SDPin)
            self.SDPin.value = False

        @property
        def enabled(self) -> bool:
            """
            flag indicating if this speaker is enabled
            """
            return self.SDPin.value

        def enable(self) -> None:
            """
            enable this speaker
            """
            self.SDPin.value = True

        def disable(self) -> None:
            """
            disable this speaker
            """
            self.SDPin.value = False

        def play(self, signal: np.ndarray, fs:float = None, force: bool = True) -> None:
            """
            play some arbitrary signal on this speaker

            Args:
                signal:
                    1D array of the signal to play on the speakers
                fs:
                    sampling rate of the provided signal
                    if specified the signal will be resampled to self.fs
                    otherwise the signal will be assumed to have sampling rate
                    self.fs
                force:
                    flag indicating to stop any playing audio to play
                    this sound
            """
            self.parent.play([self.name], signal, fs, force)

        def play_tone(self, freq: float, dur: float, volume: float = 1, force: bool = True) -> None:
            """
            play a sine tone of a specified frequency, duration and volume
            from this speaker

            Args:
                freq: float
                    desired frequency of the tone. this must not exceed the
                    Nyquist frequency for the interface (self.fs/2)
                dur:
                    desired duration of the tone
                volume:
                    value between 0 and 1 indicating the fraction
                    of max volume to play the sound at
                force:
                    flag indicating to stop any running streams to play
                    this sound
            """
            self.parent.play_tone([self.name], freq, dur, volume, force)


    def __init__(self, fs: float = 88_200):
        """
        Args:
            fs:
                sampling rate of the interface
            out_index:
                index of the audio output to use when playing sound.
                the default behavior is to use an output associated to
                an allo katana  DAC if available and otherwise use the default output
        """

        self.fs = fs
        self.speakers = {}

    @property
    def fs(self) -> float:
        """
        sampling rate in Hz
        """
        return self._fs

    @fs.setter
    def fs(self, fs: float) -> None:
        assert fs in self.SUPPORTED_FS, f"{fs} is not a supported sampling rate. Supported sampling rates are as follows: {self.SUPPORTED_FS}"
        if pygame.mixer.get_init():
            pygame.mixer.quit()
        pygame.mixer.init(channels=1, frequency = fs)
        self._fs = fs

    def add_speaker(self, name: str,  SDPin: Union[str, int]) -> Speaker:
        """
        add a speaker to the interface with the specified
        name and SDPin

        Args: 
            name:
                name to assign the speaker
            SDPin:
                pin to toggle in order to mute this speaker.
                the convention is such that when this pin is low
                the speaker is muted. when high the speaker is enabled
        Returns:
            speaker:
                reference to the speaker added to the interface
        """
        self.speakers[name] = AudioInterface.Speaker(name, self, SDPin)
        return self.speakers[name]

    def play(self, speakers: list, signal: np.ndarray, fs: float = None, force: bool = True) -> None:
        """
        play some arbitrary signal on the specified speakers

        Args:
            signal:
                1D array of the signal to play on the speakers
            speakers: list
                list of names of speakers to play the tone on
            fs:
                sampling rate of the provided signal
                if specified the signal will be resampled to self.fs
                otherwise the signal will be assumed to have sampling rate
                self.fs
            force:
                flag indicating to stop any playing audio to play
                this sound
        """

        assert isinstance(signal, np.ndarray), "signal must be a 1D numpy array"
        assert signal.ndim == 1, "signal must be a 1D numpy array"

        # if force is true stop any running streams
        if pygame.mixer.get_busy():
            if force: 
                pygame.mixer.stop()
            else: 
                return

        # enable only specified speakers
        for i in self.speakers:
            self.speakers[i].disable()
        for i in speakers:
            self.speakers[i].enable()

        # resample signal from specified sampling rate to the interface sampling rate
        if fs is not None:
            t_end = signal.size/fs
            t = np.arange(0, t_end, step = 1/fs)
            interp = interp1d(t, signal)
            t2 = np.arange(0, t_end, step = 1/self.fs)
            signal = interp(t2)

        signal = ((2**15) * np.clip(signal, -1,1)).astype('int16')
        sound = pygame.sndarray.make_sound(signal)
        sound.play()


    def play_tone(self, speakers: list, freq: float, dur: float, volume: float = 1, 
                  force: bool = True) -> None:
        """
        play a sine tone of a specified frequency, duration and volume
        on the specified speakers

        Args:
            speakers:
                list of names of speakers to play the tone on
            freq: float
                desired frequency of the tone. this must not exceed the
                Nyquist frequency for the interface (self.fs/2)
            dur:
                desired duration of the tone
            volume:
                value between 0 and 1 indicating the fraction
                of max volume to play the sound at
            force:
                flag indicating to stop any running streams to play
                this sound
        """
        if freq>=(self.fs/2):
            raise ValueError(f"the requested frequency is greater than the Nyquist frequency of interface ({self.fs/2:.2f} Hz)")  
        n_samples = int(self.fs * dur)
        t = np.arange(n_samples)/self.fs
        samples = volume * np.sin(2* np.pi * freq * t)
        self.play(speakers, samples, force=force)

    def __del__(self) -> None:
        pygame.mixer.quit()