
import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file
print("Hello World!")


api_key = os.environ.get('CHATGPT_KEY')
print("ChatGPT API KEY: ", api_key)

<<<<<<< Updated upstream
import whisper
model = whisper.load_model("base")

result = model.transcribe("harvard.wav")
result["text"]
=======



import openai
audio_file= open("/path/to/file/audio.mp3", "rb")
transcript = openai.Audio.transcribe("whisper-1", audio_file)
>>>>>>> Stashed changes
