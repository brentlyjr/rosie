import azure.cognitiveservices.speech as speechsdk
import base64
import os
import io
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

        self.audio_format = speechsdk.audio.AudioStreamFormat(samples_per_second=8000,
                                                            bits_per_sample=8,
                                                            channels=1, 
                                                            wave_stream_format=speechsdk.AudioStreamWaveFormat.MULAW)
        self.push_stream = speechsdk.audio.PushAudioInputStream(stream_format=self.audio_format)
        self.audio_config = speechsdk.audio.AudioConfig(stream=self.push_stream)
        self.pull_stream = speechsdk.audio.PullAudioOutputStream()

        self.call_sid = call_sid

    def speech_recognizer(self):
        return speechsdk.SpeechRecognizer(speech_config=self.speech_config, audio_config=self.audio_config)

    def generate_speech(self, synth_text):
        stream_config = speechsdk.audio.AudioOutputConfig(stream=self.pull_stream)
        speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=self.speech_config, audio_config=stream_config)

        # Ask Azure to translate our text into speech
        result = speech_synthesizer.speak_text_async(synth_text).get()

        # Destroys the synthesizer in order to close the output stream.
        del speech_synthesizer

        # This is our buffer where we will put the data from our stream
        data_chunk = io.BytesIO()

        # This bit of code is just pulling data off of our stream in chunks until we have read everything. As we
        # are getting those chunks of data, we are appending it to a buffer that we will encode and return to
        # transmit over the phone
        audio_buffer = bytes(32000)
        total_size = 0
        filled_size = self.pull_stream.read(audio_buffer)
        while filled_size > 0:
            data_chunk = audio_buffer[:filled_size]
            print("{} bytes received.".format(filled_size))
            total_size += filled_size
            filled_size = self.pull_stream.read(audio_buffer)
        print("Totally {} bytes received.".format(total_size))

        encoded_data = base64.b64encode(data_chunk).decode('utf-8')

        # Append this raw chunk to our audio buffer
        return encoded_data

    def write_stream(self, payload):
        # Decode our payload and append to our push stream
        self.push_stream.write(base64.b64decode(payload))
   
    def cleanup(self):
        if os.path.exists(self.synth_file_name):
            # Delete the file
            os.remove(self.synth_file_name)
            #print(f"File '{self.synth_file_name}' has been deleted.")
        else:
            print(f"The file '{self.synth_file_name}' does not exist.")   

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
