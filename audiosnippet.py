import speechrecognizer as sr
import pyaudio  # so we can access microphone and record a stream
import wave     # so we can save to a WAV file
import os       # so we can access environment variables
import pygame

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
            


class PyAudioSnippet(AudioSnippet):
    def __init__(self, filename = None, language ="english"):
        super().__init__(language)

        self.filename = filename

        self.p = pyaudio.PyAudio()
        self.sample_format = pyaudio.paInt16  # 16 bits per sample

        self.chunk = 1024  # Record in chunks of 1024 samples
        self.channels = 1    # Only one channel seems to work on our laptops
        self.fs = 44100      # Record at 44100 samples per second
    
        # Initialize the sound player
        pygame.init()
        pygame.mixer.init()

    def play_audio(self):
        # Add code here to play the audio file
        sound = pygame.mixer.Sound(self.filename)
        sound.play()

        while pygame.mixer.get_busy():
            pygame.time.Clock().tick(10)

    def record_audio(self, duration = 3):
        super().record_audio(duration)
        self.duration_in_seconds = duration
        self.frames = []     # Initialize array to store frames


        # Record data in chunks
        stream = self.p.open(format=self.sample_format,
                        channels=self.channels,
                        rate=self.fs,
                        frames_per_buffer=self.chunk,
                        input=True)

        # Store data in chunks for 3 seconds
        for i in range(0, int(self.fs / self.chunk * self.duration_in_seconds)):
            data = stream.read(self.chunk)
            self.frames.append(data)

        stream.stop_stream()
        stream.close()

        #self.p.terminate()     #Not sure where to close the resource

        self.save_audio_to_file()

    def save_audio_to_file(self, filename="temp/temp-audio.wav"):
            self.filename = filename

            wf = wave.open(filename, 'wb')
            wf.setnchannels(self.channels)
            wf.setsampwidth(self.p.get_sample_size(self.sample_format))
            wf.setframerate(self.fs)
            wf.writeframes(b''.join(self.frames))
            wf.close()

    def translate_to_text(self):
        text = self.speech_recognizer.translate_to_text(self.filename)
        return text

    def add_audio(self, file):
        self.filename = file
      