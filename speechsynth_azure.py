import io
import threading
import azure.cognitiveservices.speech as speechsdk


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
