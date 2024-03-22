from elevenlabs.client import ElevenLabs
import base64


class SpeechSynthEleven:
    def __init__(self, SPEECH_KEY, _, call_sid):
        self.call_sid = call_sid
        self.client = ElevenLabs(api_key=SPEECH_KEY) 

    def generate_speech(self, synth_text):
        audio_stream = self.client.generate(
            text=synth_text,
            voice="George",
            output_format = 'ulaw_8000',
            stream=True
            )
        collected_data = [data for data in audio_stream]
        print("about to get data length of list")
        data_size = len(collected_data)

        audio = b''

        for data in collected_data:
            audio += data
        
        encoded_data = base64.b64encode(audio).decode('utf-8')
        return encoded_data
   
    # Call this in our loop and if there is data to be transmitted, we will put it on the websocket, this
    # is the code needed for streaming the incoming synthesized speech
    def get_outbound_speech():
        return None
    

    def play_digit(self, digit):
        dest_filename_template = "phone_sounds/audacity-ulaw-break/digit-{digit}.raw"
        dest_digit_file = dest_filename_template.format(digit=digit)

        print(f"Playing sound for digit-{digit}")
        with open(dest_digit_file, 'rb') as binary_file:
            data_chunk = binary_file.read()
            encoded_data = base64.b64encode(data_chunk).decode('utf-8')
        return encoded_data

    def play_eleven(self):
        filename = "eleven.ulaw"

        print(f"Playing eleven_labs audio")
        with open(filename, 'rb') as binary_file:
            data_chunk = binary_file.read()
            encoded_data = base64.b64encode(data_chunk).decode('utf-8')
        return encoded_data

    def write_stream(self, payload):
        # Decode our payload and append to our array
        # Write data to speech recognizer stream
        self.stream.write(base64.b64decode(payload))
        self.audio_to_file.add_data(base64.b64decode(payload), 'right')
   
   # I don't think this gets called anywhere.  Remove?
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
