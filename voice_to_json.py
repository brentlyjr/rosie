# voice_to_json.py

import pyaudio  # so we can access microphone and record a stream
import wave     # so we can save to a WAV file
import os       # so we can access environment variables

def voice_to_json():
    chunk = 1024  # Record in chunks of 1024 samples
    sample_format = pyaudio.paInt16  # 16 bits per sample
    channels = 1    # Only one channel seems to work on our laptops
    fs = 44100      # Record at 44100 samples per second
    seconds = 3     # 3 seconds of data
    filename = "temp/temp_file_recording.wav"
    temppath = "temp"

    # import our environment variables and get our API key for ChatGPT access
    from dotenv import load_dotenv
    load_dotenv()  # Load environment variables from .env file
    api_key = os.environ.get('CHATGPT_KEY')
    if not os.path.exists(temppath):
        os.mkdir(temppath)  

    # Create an interface to PortAudio
    p = pyaudio.PyAudio()

    print('Recording')

    # Record data in chunks
    stream = p.open(format=sample_format,
                    channels=channels,
                    rate=fs,
                    frames_per_buffer=chunk,
                    input=True)

    frames = []  # Initialize array to store frames

    # Store data in chunks for 3 seconds
    for i in range(0, int(fs / chunk * seconds)):
        data = stream.read(chunk)
        frames.append(data)

    # Stop and close the stream 
    stream.stop_stream()
    stream.close()

    # Terminate the PortAudio interface
    p.terminate()

    print('Finished recording')

    # Save the recorded data as a temporary WAV file
    wf = wave.open(filename, 'wb')
    wf.setnchannels(channels)
    wf.setsampwidth(p.get_sample_size(sample_format))
    wf.setframerate(fs)
    wf.writeframes(b''.join(frames))
    wf.close()

    # Take the file we just created and send it to Whisper API for transcribing
    import openai

    openai.api_key = api_key
    audio_file= open(filename, "rb")
    transcript = openai.Audio.transcribe("whisper-1", audio_file)

    return transcript

