from abc import ABC, abstractmethod
from dotenv import load_dotenv
import os
import openai


class SpeechRecognizer(ABC):
    def __init__(self, language):
        self.language = language

    @abstractmethod
    def translate_to_text(self, filename):
        pass


class WhisperRecognizer(SpeechRecognizer):

    def __init__(self, language):
        super().__init__(language)
        load_dotenv()  # Load environment variables from .env file
        self.api_key = os.environ.get('CHATGPT_KEY')

    def translate_to_text(self, filename):
        openai.api_key = self.api_key
        with open(filename, "rb") as audio_file:
            transcript = openai.Audio.transcribe("whisper-1", audio_file)
        return transcript
