import io
import base64
import time
import string
import random
import threading
import azure.cognitiveservices.speech as speechsdk
from collections import deque

class SpeechSynthAzure(SpeechSynth):  
    def __init__(self, call_sid, *args, **kwargs):
        super().__init__(call_sid)

class SpeechSynthAzure:

    def __init__(self, speech_config, synth_text, status, call_sid):

        self.synth_text = synth_text
        self.call_sid = call_sid
        self.speech_config = speech_config
        self._header_offset = 0 #46
        self.total_byte_size = 0
        self.status = status    # Type of synth token this is (0 = middle of stream, 1 = end of sentence, 2 = end of conversation/goodbye)

        # We need to make sure our reads and writes are thread safe
        self.buffer_lock = threading.Lock()

        # When our synthesis is done, we know we can take it off the queue
        self.still_synthesizing = True

        self.pull_stream = speechsdk.audio.PullAudioOutputStream()

        stream_config = speechsdk.audio.AudioOutputConfig(stream=self.pull_stream)
        self.speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=self.speech_config, audio_config=stream_config)

        # self.speech_synthesizer.synthesis_started.connect(lambda evt: print('SYNTHESIS STARTED: {}'.format(evt)))
        # self.speech_synthesizer.synthesis_canceled.connect(lambda evt: print('SYNTHESIS CANCELED: {}'.format(evt)))
        self.speech_synthesizer.synthesis_completed.connect(self.synthesis_completed_cb)
        self.speech_synthesizer.synthesizing.connect(self.synthesis_synthesizing_cb)
        # self.speech_synthesizer.synthesis_word_boundary.connect(lambda evt: print('SYNTHESIS WORD BOUNDARY: {}'.format(evt)))

        # Start synthesizing this text - as soon as we have data, our callbacks will be triggered
        self.result = self.speech_synthesizer.start_speaking_text_async(synth_text)

        # This is our buffer that holds all the data being synthesized for this specific chunk
        self.synthesis_buffer = io.BytesIO()
        self.current_read_position = 0

    def synthesis_completed_cb(self, evt):
        # print('SYNTHESIS COMPLETED: {}'.format(evt))

        # Mark ourselves done so our manager will know to clean up the queue later
        self.still_synthesizing = False

        # Clean up our synthesis objects
        del self.speech_synthesizer
        del self.result

        '''        
        # This is debuggin code, I am just trying to see if I generate multiple objects successfully
        # Save our raw buffer out to a file. This is Signed 16-Bit PCM, No Endian, 16K, 1 Channel
        current_time = int(time.time())

        # Generate a random string of characters
        random_string = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))

        # Concatenate the timestamp and random string to create the filename
        filename = str(current_time) + random_string + ".bin"
        print("Saving to file: " + filename)

        with open(filename, 'wb') as f:
            f.write(self.synthesis_buffer.getvalue())
        '''

    def synthesis_synthesizing_cb(self, evt):
        # print('SYNTHESIS SYNTHESIZING: {}'.format(evt))

        data_size = len(evt.result.audio_data)
        chunk_size = data_size - self._header_offset
        # print("Synthesizing (data_size =",data_size,") (chunk_size=",chunk_size,") (total_size=",self.total_byte_size,") - ",self.synth_text)

        if chunk_size > 0:
            self.total_byte_size += chunk_size

            # Lock our write thread so someone doesn't try to read at the same time and mess up our position
            with self.buffer_lock:
                self.synthesis_buffer.write(evt.result.audio_data[-chunk_size:])

    def get_data(self):
        with self.buffer_lock:
            # Get the current write position in the buffer
            current_write_position = self.synthesis_buffer.tell()

            # Read all the additional data that has been added since the last read
            self.synthesis_buffer.seek(self.current_read_position)  # Move to the beginning of the buffer
            additional_data = self.synthesis_buffer.read(current_write_position)  # Read the data up to the current position
            self.synthesis_buffer.seek(current_write_position)
            self.current_read_position = current_write_position
            return additional_data

    def get_text(self):
        return self.synth_text


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
