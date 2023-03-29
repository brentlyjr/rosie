
import os
from dotenv import load_dotenv
from voice_to_json import voice_to_json

load_dotenv()  # Load environment variables from .env file
print("Hello World!")

# Test load our Environment variable and print it out
api_key = os.environ.get('CHATGPT_KEY')
print("ChatGPT API KEY: ", api_key)


# Call our function that will record 3 secnds of audio from the microphone and return it as a JSON object
transcript = voice_to_json()
print(transcript)
