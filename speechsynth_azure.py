import base64
import azure.cognitiveservices.speech as speechsdk
from rosie_utils import load_environment_variable
from speechsynth import SpeechSynth

class SpeechSynthAzure(SpeechSynth):  
    def __init__(self, call_sid, *args, **kwargs):
        super().__init__(call_sid)

        SPEECH_KEY = load_environment_variable("AZURE_SPEECH_KEY")
        SPEECH_REGION = load_environment_variable("AZURE_SPEECH_REGION")

        self.speech_config = speechsdk.SpeechConfig(subscription=SPEECH_KEY, region=SPEECH_REGION)

        # We want the stream back in 8-bit 8000K uLaw with a single channel (mono)
        self.speech_config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Raw8Khz8BitMonoMULaw)

        # Choose the Emma english US voice
        self.speech_config.speech_synthesis_voice_name="en-US-EmmaNeural"

        # Let's allow swearing to come through
        self.speech_config.set_profanity(speechsdk.ProfanityOption.Raw)

    
    def generate_speech(self, synth_text):
        # Implementation specific to Azure
        pcm_data = self._generate_speech_raw_pcm(synth_text)

        encoded_data = base64.b64encode(pcm_data).decode('utf-8')
        return encoded_data


    def _generate_speech_raw_pcm(self, synth_text):
        # Our pull stream is where we can fetch the data as it is synthesized
        pull_stream = speechsdk.audio.PullAudioOutputStream()

        stream_config = speechsdk.audio.AudioOutputConfig(stream=pull_stream)
        speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=self.speech_config, audio_config=stream_config)

        # Ask Azure to translate our text into speech
        result = speech_synthesizer.speak_text_async(synth_text).get()

        # Destroys the synthesizer in order to close the output stream.
        del speech_synthesizer

        # This is our buffer where we will put the data from our stream
        big_buffer = bytearray()

        # This bit of code is just pulling data off of our stream in chunks until we have read everything. As we
        # are getting those chunks of data, we are appending it to a buffer that we will encode and return to
        # transmit over the phone
        audio_buffer = bytes(32000)
        total_size = 0
        filled_size = pull_stream.read(audio_buffer)
        print("Writing ", filled_size, " bytes to buffer of size ", total_size)
        while filled_size > 0:
            big_buffer.extend(audio_buffer[:filled_size])
            total_size += filled_size
            filled_size = pull_stream.read(audio_buffer)
            print("Writing ", filled_size, " bytes to buffer of size ", total_size)

        return big_buffer

    def cleanup(self):
        pass