import azure.cognitiveservices.speech as speechsdk
import base64
import os

class SpeechSynthAzure:
    def __init__(self, SPEECH_KEY, SPEECH_REGION):
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
        self.stream = speechsdk.audio.PushAudioInputStream(stream_format=self.audio_format)
        self.audio_config = speechsdk.audio.AudioConfig(stream=self.stream)

    def speech_recognizer(self):
        return speechsdk.SpeechRecognizer(speech_config=self.speech_config, audio_config=self.audio_config)

    def generate_speech(self, synth_text):
        file_config = speechsdk.audio.AudioOutputConfig(filename=self.synth_file_name)
        speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=self.speech_config, audio_config=file_config)

        result = speech_synthesizer.speak_text_async(synth_text).get()

        with open(self.synth_file_name, 'rb') as binary_file:
            data_chunk = binary_file.read()
            encoded_data = base64.b64encode(data_chunk).decode('utf-8')

        return encoded_data

    def write_stream(self, payload):
        # Decode our payload and append to our array
        self.stream.write(base64.b64decode(payload))

    def cleanup(self):
        if os.path.exists(self.synth_file_name):
            # Delete the file
            os.remove(self.synth_file_name)
            #print(f"File '{self.synth_file_name}' has been deleted.")
        else:
            print(f"The file '{self.synth_file_name}' does not exist.")   