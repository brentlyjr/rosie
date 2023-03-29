import pyaudio  # so we can access microphone and record a stream
import wave     # so we can save to a WAV file
import os       # so we can access environment variables

class AudioRecording:
    def __init__(self)):
        self.chunk = 1024  # Record in chunks of 1024 samples
        self.sample_format = pyaudio.paInt16  # 16 bits per sample
        self.channels = 1    # Only one channel seems to work on our laptops
        self.fs = 44100      # Record at 44100 samples per second
        self.seconds = 3     # 3 seconds of data
        self.frames = []     # Initialize array to store frames

    def record_audio(self, filename="temp_file_recording.wav"):
        self.filename = "temp/" & filename
        self.start_audio()
        self.stop_stream()
        self.close_recorder()
        self.generate_audio_file();

        return self.


    def start_audio(self):
        # Create an interface to PortAudio
        self.p = pyaudio.PyAudio()

        print('Recording')
        # Record data in chunks
        stream = self.p.open(format=self.sample_format,
                        channels=self.channels,
                        rate=self.fs,
                        frames_per_buffer=self.chunk,
                        input=True)


        

        # Store data in chunks for 3 seconds
        for i in range(0, int(self.fs / self.chunk * self.seconds)):
            data = stream.read(self.chunk)
            self.frames.append(self.data)

    # Stop and close the stream 
    def stop_stream(self)
        stream.stop_stream()
        stream.close()

    # Terminate the PortAudio interface
    def close_recorder(self):
        self.p.terminate()
         print('Finished recording')    
   

    # Save the recorded data as a temporary WAV file
    def generate_audio_file(self):
        temppath = "temp"

        if not os.path.exists(temppath):
            os.mkdir(temppath)  

        wf = wave.open(self.filename, 'wb')
        wf.setnchannels(self.channels)
        wf.setsampwidth(self.p.get_sample_size(self.sample_format))
        wf.setframerate(self.fs)
        wf.writeframes(b''.join(self.frames))
        wf.close()

    # Take the file we just created and send it to Whisper API for transcribing

import openai
from dotenv import load_dotenv

class TexttoSpeach():
    def __init__(self):
        load_dotenv()  # Load environment variables from .env file
        self.openai_api_key = os.environ.get('CHATGPT_KEY')


    def audio_file_to_text(self, filename):      
        audio_file = open(filename, "rb")
        openai.api_key = self.openai_api_key
        transcript = openai.Audio.transcribe("whisper-1", audio_file)

        return transcript
