
import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file
print("Hello World!")


api_key = os.environ.get('CHATGPT_KEY')
print("ChatGPT API KEY: ", api_key)

import openai

audio_file= open("./harvard.wav", "rb")
openai.api_key = api_key
transcript = openai.Audio.transcribe("whisper-1", audio_file)

print(transcript)
