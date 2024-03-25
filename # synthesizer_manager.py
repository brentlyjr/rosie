# synthesizer_manager.py

# This class is how we manage multiple chunks of text being synthesized at the same time
class SynthesizerManager:

    def __init__(self, SPEECH_KEY, SPEECH_REGION, call_sid):
        # Create oru speech_config for our voice synthesis
        self.speech_config = speechsdk.SpeechConfig(subscription=SPEECH_KEY, region=SPEECH_REGION)

        # We want the stream back in 8-bit 8000K uLaw with a single channel (mono)
        self.speech_config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Raw8Khz8BitMonoMULaw)

        # Choose the Emma english US voice
        self.speech_config.speech_synthesis_voice_name="en-US-EmmaNeural"

        # Let's allow swearing to come through
        self.speech_config.set_profanity(speechsdk.ProfanityOption.Raw)

        # A queue of keep all of our active Speech Synthesizers
        self.synthesizer_queue = deque()

        # Save our id for this call
        self.call_sid = call_sid

        synth_config = load_config('Synth')
        # speech_synth = get_speech_synth_service(synth_config['provider'], call_sid, voice=synth_config['voice'])

    def get_speech_synth_service(synth_type, call_sid, *args, **kwargs):
        """
        Generates the correct SpeechSynth subclass and returns subclass object
            synth_type - shortened name of subclass, e.ge Azure, Eleven 
            subclass   then generated , e.g. SpeechSynthAzure, SpeechSynthEleven
        """
        class_name = f'SpeechSynth{synth_type}'
        
        # Try to get the class from globals() where all global symbols are stored
        # You might prefer locals() if the class is defined in a local scope
        SynthClass = globals().get(class_name)

        if SynthClass is not None and issubclass(SynthClass, SpeechSynth):
            return SynthClass(call_sid=call_sid, *args, **kwargs)
        else:
            raise ValueError(f"Unsupported speech synthesis service type: {synth_type}")

    # Take a new chunk of text and push this into a speech synthesizer
    def synthesize_speech(self, synth_text, status):
        # print("Synthesizing text: ", synth_text)

        # Create a new syntesizer - this will automaticallys start synthesizing the speech and
        # save it to its local buffer
        new_synthesizer = SpeechSynthAzure(self.speech_config, synth_text, status, self.call_sid)

        # Add it to the end of our queue
        self.synthesizer_queue.append(new_synthesizer)

    def get_more_synthesized_data(self):
        return_status = 0

        # Only do this if we have more items in our queue
        if self.synthesizer_queue:
            # Get the first object in our queue
            first_object = self.synthesizer_queue[0]

            data = first_object.get_data()
            size = len(data)
            if size == 0:
                # No data and we are not synthesizing anymore, so we can remove it from the queue
                if first_object.still_synthesizing == False:
                    self.synthesizer_queue.popleft()
                    return_status = first_object.status
            else:
                return data, first_object.status

        # If everything is empty, then we have more more data at this time
        return None, return_status

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
        return seconds + 2      # TODO: Need another two seconds to get last of data (better way?)
