import base64
from abc import ABC, abstractmethod

class SpeechSynth(ABC):
    def __init__(self, call_sid):
        self.call_sid = call_sid
        
    @abstractmethod
    def generate_speech(self, synth_text):
        pass

    @abstractmethod
    def cleanup(self):
        pass
        
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

    def write_stream(self, payload):
        # Decode our payload and append to our array
        # Write data to speech recognizer stream
        self.stream.write(base64.b64decode(payload))
        self.audio_to_file.add_data(base64.b64decode(payload), 'right')

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