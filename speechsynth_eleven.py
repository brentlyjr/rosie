from elevenlabs.client import ElevenLabs
import base64
from rosie_utils import load_environment_variable
from speechsynth import SpeechSynth
import sys
from io import StringIO


class SpeechSynthEleven(SpeechSynth):
    def __init__(self, call_sid, *args, **kwargs):
        super().__init__(call_sid)
        SPEECH_KEY = load_environment_variable("ELEVEN_SPEECH_KEY")
        self.client = ElevenLabs(api_key=SPEECH_KEY)
        self.voice = kwargs.get('voice', 'George')
    
    def generate_speech(self, synth_text):
        # put client.generate function in the try block to silence all the information
        # the api is streaming to the console.

        original_stdout = sys.stdout
        try:
            # Redirect stdout to silence unwanted prints
            sys.stdout = StringIO()

            audio_stream = self.client.generate(
                text=synth_text,
                voice=self.voice,
                output_format = 'ulaw_8000',
                stream=True
                )
            # Optionally capture the output if needed
            # captured_output = sys.stdout.getvalue()
        finally:
            # Restore stdout back to original
            sys.stdout = original_stdout

        collected_data = [data for data in audio_stream]
        print("about to get data length of list")
        data_size = len(collected_data)

        audio = b''

        for data in collected_data:
            audio += data
        
        encoded_data = base64.b64encode(audio).decode('utf-8')
        return encoded_data
   
    # I don't think this gets called anywhere.  Remove?
    def cleanup(self):
        pass