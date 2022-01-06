#!/usr/bin/env python
"""Play a fixed frequency sound."""
from __future__ import division
from ctypes import *
from contextlib import contextmanager
import math

from pyaudio import PyAudio # sudo apt-get install python{,3}-pyaudio

try:
    from itertools import izip
except ImportError: # Python 3
    izip = zip
    xrange = range
    
# From alsa-lib Git 3fd4ab9be0db7c7430ebd258f2717a976381715d
# $ grep -rn snd_lib_error_handler_t
# include/error.h:59:typedef void (*snd_lib_error_handler_t)(const char *file, int line, const char *function, int err, const char *fmt, ...) /* __attribute__ ((format (printf, 5, 6))) */;
# Define our error handler type

class audioObject:
    def __init__(self, highFrequency = 8000.00 , lowFrequency = 900):
        self.highFrequency = 8000.00
        self.lowFrequency = 900.00 

    def sine_tone(self, frequency, duration, volume=1, sample_rate=22050):
        n_samples = int(sample_rate * duration)
        restframes = n_samples % sample_rate
        p = PyAudio() 
        stream = p.open(format=p.get_format_from_width(1), # 8bit
                        channels=1, # mono
                        rate=sample_rate,
                        output=True)
        s = lambda t: volume * math.sin(2 * math.pi * frequency * t / sample_rate)
 
        samples = (int(s(t) * 0x7f + 0x80) for t in range(n_samples))  
        stream.write(bytes(bytearray(samples)))

        # fill remainder of frameset with silence
        stream.write(b'\x80' * restframes)
        stream.stop_stream()
        stream.close()
        p.terminate()

        

