import speechrecognizer as sr
import os       # so we can access environment variables
import sounddevice as sd
import numpy
import time
from scipy.io.wavfile import read, write

class AudioSnippet:
    def __init__(self, language="english"):
        self.speech_recognizer = sr.WhisperRecognizer(language)

    def play_audio(self, file_path):
        # Add code here to play the audio file
        pass

    def record_audio(self, duration):
        # Add code here to record audio for the specified duration
        pass

    def translate_to_text(self):
        # Add code here to translate the audio_data to text using the SpeechRecognizer
        pass

    def save_audio_to_file(self, filename):
        pass

    def get_file(self):
        # Add code here to get the audio file from the specified file path
        if self.filename:
            return self.filename
        else:
            return "Error: Filename not found"
                  

class SDAudioSnippet(AudioSnippet):
    def __init__(self, filename = None, language ="english"):
        super().__init__(language)

        self.filename = filename

        self.fs = 44100


    def play_audio(self):
        # Add code here to play the audio file
        device_index = self.get_device(sd.query_devices(), 'speaker')
        sd.play(self.myrecording, self.fs, device=device_index)

    def record_audio(self, duration = 3):
        super().record_audio(duration)
        self.duration_in_seconds = duration

        device_index = self.get_device(sd.query_devices(), 'microphone')
        self.myrecording = sd.rec(int(duration*self.fs), samplerate=self.fs, channels=1, device =device_index)
        self.countdown(duration)
        self.save_audio_to_file()

    def save_audio_to_file(self, filename="temp/temp-audio.wav"):
            self.filename = filename

            write(filename, self.fs, self.myrecording)

    def translate_to_text(self):
        text = self.speech_recognizer.translate_to_text(self.filename)
        return text

    def add_audio(self, file):
        self.filename = file
        self.fs, self.myrecording = read(file)
    
    def get_device(self, sound_devices, search_string):
        search_string = search_string.lower()
        for i, device in enumerate(sound_devices):
            if search_string in device['name'].lower():
                return i
        return None
    
    def get_audio(self):
        return self.myrecording
    
    def countdown(self, seconds):
        for i in range(seconds, 0, -1):
            print(f"Recording for {i} seconds", end='\r')
            time.sleep(1)
        print("Recording finished.             ")