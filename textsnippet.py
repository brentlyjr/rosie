#import speechsynthesizer as synth


class TextSnippet:
    def __init__(self, text= "",language="english"):
        self.speech_synth = synth.SpeechSynth(language)
        self.text = text
        self.language = language

    def __str__(self):
        return self.text
    
    def get_text(self):
        # Add code here to play the audio file
        return self.text
    
    def add_text(self, text):
        # Add code here to record audio for the specified duration
        self.text += " " + (text)

    def translate_to_speech(self):
        # Add code here to translate the audio_data to text using the SpeechRecognizer
        return self.speech_synth(self.text)
