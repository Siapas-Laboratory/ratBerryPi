#######################################
#
# code influenced by https://stackoverflow.com/questions/974071/python-library-for-playing-fixed-frequency-sound
# 
# Desiderio Ascencio 
#######################################

"""Play a fixed frequency sound."""
import numpy as np
import pyaudio as pa  # sudo apt-get install python{,3}-pyaudio
import RPi.GPIO as GPIO



class AudioInterface:
    def __init__(self, fs = 22050):
        self.session = pa.PyAudio()
        self.fs = fs
        self.stream = None
        self.SDPins = []


    def play_tone(self, freq, dur, volume=1, SDPin = None, force = True):

        if self.stream:
            if self.stream.is_active():
                if force:
                    self.stream.stop_stream()
                    self.stream.close()
                    for i in self.SDPins:
                        GPIO.output(i, GPIO.LOW)
                else:
                    return
        if SDPin:
            GPIO.output(SDPin, GPIO.HIGH)
            if SDPin not in self.SDPins: self.SDPins.append(SDPin)

        n_samples = int(self.fs * dur)
        restframes = n_samples % self.fs
        t = np.arange(n_samples)/self.fs
        self.samples = volume * np.sin(2* np.pi * freq * t)
        self.samples = np.concatenate((self.samples, np.zeros(restframes))).astype(np.float32).tobytes()


        def callback(in_data, frame_count, time_info, status):
            if len(self.samples)>0:
                nbytes = int(frame_count * 4)
                data = self.samples[:nbytes]
                self.samples = self.samples[nbytes:]
                return (data, pa.paContinue)
            else:
                print(frame_count)
                for i in self.SDPins:
                    GPIO.output(i, GPIO.LOW)
                return (None, pa.paComplete)

        self.stream = self.session.open(format = pa.paFloat32,
                                      channels = 1,
                                      rate = self.fs,
                                      output = True,
                                      stream_callback = callback)

        self.stream.start_stream()

    def __del__(self):
        self.stream.close()
        self.session.terminate()

        
class Speaker:
    def __init__(self, name, audio_interface, SDPin):
        self.name = name
        self.audio_interface = audio_interface
        self.SDPin = SDPin
        GPIO.setup(self.SDPin, GPIO.OUT)
        GPIO.output(self.SDPin, GPIO.LOW)

    def play_tone(self, freq, dur, volume=1, force = True):
        self.audio_interface.play_tone(freq, dur, volume=volume, SDPin=self.SDPin)

