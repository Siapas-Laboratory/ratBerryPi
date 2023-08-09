#######################################
#
# code influenced by https://stackoverflow.com/questions/974071/python-library-for-playing-fixed-frequency-sound
# 
# Desiderio Ascencio 
#######################################

"""Play a fixed frequency sound."""
import numpy as np
from pyaudio import PyAudio, paFloat32 # sudo apt-get install python{,3}-pyaudio
import RPi.GPIO as GPIO




class AudioInterface:
    def __init__(self, fs = 22050):
        self.audio = PyAudio()
        self.fs = fs
        self.stream = self.audio.open(format = paFloat32,
                                      channels = 1,
                                      rate = self.fs,
                                      output = True)
        self.SDPins = []
        
    def play_tone(self, freq, dur, volume=1, SDPin = None):

        if self.stream.is_active():
            self.stream.stop_stream()

        for i in self.SDPins:
            GPIO.output(i, GPIO.LOW)

        if SDPin:
            GPIO.output(SDPin, GPIO.LOW)
            if SDPin not in self.SDPins: self.SDPins.append(SDPin)

        n_samples = int(self.fs * dur)
        restframes = n_samples % self.fs
        t = np.arange(n_samples)/self.fs
        samples = volume * np.sin(2* np.pi * freq * t)
        samples = samples.astype(np.float32).tobytes()
        self.stream.write(samples)
        # fill remainder of frameset with silence
        self.stream.write(b'\x80' * restframes)
        self.stream.stop_stream()
        if SDPin:
            GPIO.output(SDPin, GPIO.LOW)

    def __del__(self):
        self.stream.close()
        self.audio.terminate()

        
class Speaker:
    def __init__(self, audio_jack, SDPin):
        self.audio_jack = audio_jack
        self.SDPin = SDPin
        GPIO.setup(self.SDPin, GPIO.OUT)
        GPIO.output(self.SDPin, GPIO.LOW)

    def play_tone(self, freq, dur, volume=1):
        self.audio_jack.play_tone(freq, dur, volume=volume)

