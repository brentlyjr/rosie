import azure.cognitiveservices.speech as speechsdk
import base64


class SpeechSynthAzure:
    def __init__(self, SPEECH_KEY, SPEECH_REGION, call_sid):

        # Creeate oru speech_config for our voice synthesis
        self.speech_config = speechsdk.SpeechConfig(subscription=SPEECH_KEY, region=SPEECH_REGION)

        # We want the stream back in 8-bit 8000K uLaw with a single channel (mono)
        self.speech_config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Raw8Khz8BitMonoMULaw)

        # Choose the Emma english US voice
        self.speech_config.speech_synthesis_voice_name="en-US-EmmaNeural"

        # Let's allow swearing to come through
        self.speech_config.set_profanity(speechsdk.ProfanityOption.Raw)

        self.call_sid = call_sid

    def generate_speech_raw_pcm(self, synth_text):
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

    def generate_speech(self, synth_text):
        pcm_data = self.generate_speech_raw_pcm(synth_text)

        encoded_data = base64.b64encode(pcm_data).decode('utf-8')
        return encoded_data
   
    # Call this in our loop and if there is data to be transmitted, we will put it on the websocket, this
    # is the code needed for streaming the incoming synthesized speech
    def get_outbound_speech():
        return None
    
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
