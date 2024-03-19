import azure.cognitiveservices.speech as speechsdk
import base64
import os
import audioop
import wave
import numpy as np

class SpeechSynthAzure:
    def __init__(self, SPEECH_KEY, SPEECH_REGION, call_sid):
        self.speech_config = speechsdk.SpeechConfig(subscription=SPEECH_KEY, region=SPEECH_REGION)

        #Added for speech synthesis
        self.speech_config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Raw8Khz8BitMonoMULaw)
        self.synth_file_name = "synth_text.bin"
        self.speech_config.speech_synthesis_voice_name="en-US-EmmaNeural" 

        # Let's allow swearing to come through
        self.speech_config.set_profanity(speechsdk.ProfanityOption.Raw)

        #Setup for speech recognition
        self.audio_format = speechsdk.audio.AudioStreamFormat(samples_per_second=8000,
                                                            bits_per_sample=8,
                                                            channels=1, 
                                                            wave_stream_format=speechsdk.AudioStreamWaveFormat.MULAW)
        self.stream = speechsdk.audio.PushAudioInputStream(stream_format=self.audio_format)
        self.audio_config = speechsdk.audio.AudioConfig(stream=self.stream)
        self.audio_to_file = ContinuousStereoWriter(call_sid, sampwidth=2, framerate=8000)

        self.call_sid = call_sid

    def speech_recognizer(self):
        return speechsdk.SpeechRecognizer(speech_config=self.speech_config, audio_config=self.audio_config)

    def generate_speech(self, synth_text):
        file_config = speechsdk.audio.AudioOutputConfig(filename=self.synth_file_name)
        speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=self.speech_config, audio_config=file_config)

        result = speech_synthesizer.speak_text_async(synth_text).get()

        with open(self.synth_file_name, 'rb') as binary_file:
            data_chunk = binary_file.read()
            encoded_data = base64.b64encode(data_chunk).decode('utf-8')

        self.audio_to_file.add_data(data_chunk, 'left')
        return encoded_data

    def play_digit(self, digit):
        dest_filename_template = "phone_sounds/audacity-ulaw-break/digit-{digit}.raw"
        dest_digit_file = dest_filename_template.format(digit=digit)

        print(f"Playing sound for digit-{digit}")
        with open(dest_digit_file, 'rb') as binary_file:
            data_chunk = binary_file.read()
            encoded_data = base64.b64encode(data_chunk).decode('utf-8')
        return encoded_data


    def write_stream(self, payload):
        # Decode our payload and append to our array
        # Write data to speech recognizer stream
        self.stream.write(base64.b64decode(payload))
        self.audio_to_file.add_data(base64.b64decode(payload), 'right')
   
    def cleanup(self):
        if os.path.exists(self.synth_file_name):
            # Delete the file
            os.remove(self.synth_file_name)
            #print(f"File '{self.synth_file_name}' has been deleted.")
        else:
            print(f"The file '{self.synth_file_name}' does not exist.")   

    def stop_recording(self):
        self.audio_to_file.close()

    def time_to_speak(self, text):
        """
        Estimates the time to speak the given text aloud.
        
        :param text: The text to be spoken.
        :return: The estimated time in seconds to speak the text.
        """
        words_per_minute = 150
        words = text.split()
        number_of_words = len(words)
        minutes = number_of_words / words_per_minute
        seconds = minutes * 60  # Convert minutes to seconds
        return seconds
    
"""     def write_wav(self, raw_data):
        # Parameters for the output WAV file
        channels = 1
        sample_width = 2  # After decoding, Mu-Law results in 16 bits = 2 bytes per sample
        framerate = 8000  # 8kHz
        compname = "NONE"
        comptype = "NONE"
        
        destination_dir = "saved_audio"
        base_filename = "synth_audio"
        if not os.path.exists(destination_dir):
            os.makedirs(destination_dir)
        
        # Find the next available sequential number for the new filename
        counter = 1
        while True:
            new_filename = f"{base_filename}_{counter}.wav"  # Assuming .audio extension, change as needed
            destination_file = os.path.join(destination_dir, new_filename)
            if not os.path.exists(destination_file):
                break
            counter += 1

        # Decode Mu-Law to linear PCM
        decoded_data = audioop.ulaw2lin(raw_data, 2)
       
        with wave.open(destination_file, "w") as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(framerate)
            wav_file.setcomptype(comptype, compname)
            wav_file.writeframes(decoded_data)

        print(f"Converted to {destination_file}")
  """       

class ContinuousStereoWriter:
    def __init__(self, call_sid, sampwidth=2, framerate=8000):
        self.sampwidth = sampwidth
        self.framerate = framerate
        self.channels = 2  # Stereo
        self.buffer_left = np.array([], dtype=np.int16)
        self.buffer_right = np.array([], dtype=np.int16)
        self.call_sid = call_sid


    def add_data(self, data, channel='left'):
        # added to convert mulaw to wav
        # Currently channel left is generated speech and right is human audio

        data = audioop.ulaw2lin(data, 2)

        # Convert raw bytes to numpy array
        new_data = np.frombuffer(data, dtype=np.int16)
        
        #print("Writing data, channel", channel, " size: ", len(data), " leftbuffer: ", len(self.buffer_left), " rightbuffer: ", len(self.buffer_right))

        if channel == 'left':
            self.buffer_left = np.append(self.buffer_left, new_data)
            # Pad the right buffer with zeros to match the new left buffer length
            #pad_length = len(self.buffer_left) - len(self.buffer_right)
            #if pad_length > 0:
            #    self.buffer_right = np.append(self.buffer_right, np.zeros(pad_length, dtype=np.int16))
        elif channel == 'right':
            self.buffer_right = np.append(self.buffer_right, new_data)
            # Pad the left buffer with zeros to match the new right buffer length
            pad_length = len(self.buffer_right) - len(self.buffer_left)
            if pad_length > 0:
                self.buffer_left = np.append(self.buffer_left, np.zeros(pad_length, dtype=np.int16))
                self.write_data()

    def write_data(self):
        # Ensure both buffers are the same length before writing
        if len(self.buffer_left) == len(self.buffer_right):
            # Interleave and write the data
            stereo_data = np.column_stack((self.buffer_left, self.buffer_right)).ravel()
            self.check_open_file()
            self.output_wave.writeframes(stereo_data.tobytes())

            # Clear the buffers
            self.buffer_left = np.array([], dtype=np.int16)
            self.buffer_right = np.array([], dtype=np.int16)
        else:
            print("Buffers not the same size - no writing wave")

    def check_open_file(self):
        if not hasattr(self, 'output_wave'):
            destination_dir = "saved_audio"
            # Our wav file will be named after the unique CallSid given to this specific phone call
            base_filename = f"{self.call_sid}.wav"

            if not os.path.exists(destination_dir):
                os.makedirs(destination_dir)
            
            self.output_file = os.path.join(destination_dir, base_filename)
            self.output_wave = wave.open(self.output_file, 'wb')
            self.output_wave.setnchannels(self.channels)
            self.output_wave.setsampwidth(self.sampwidth)
            self.output_wave.setframerate(self.framerate)

    def close(self):
        #check to see if any remaining audio to write
        if len(self.buffer_left):
            # Pad the right buffer with zeros to match the new left buffer length
            pad_length = len(self.buffer_left) - len(self.buffer_right)
            if pad_length > 0:
                self.buffer_right = np.append(self.buffer_right, np.zeros(pad_length, dtype=np.int16))
                self.write_data()
                
        if hasattr(self, 'output_wave') and self.output_wave is not None:
            self.output_wave.close()  
            delattr(self, 'output_wave')
            self.buffer_left = np.array([], dtype=np.int16)
            self.buffer_right = np.array([], dtype=np.int16)
            print("closed and deleted attribute")
        
        