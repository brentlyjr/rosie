# Program to accept a phone call via Twilio and save what the speaker says to a WAVE file.
# That wave file is then sent to Twilio after the call terminates and is transcribed and the result printed to the console
# Need to have ngrok, FastAPI and Twilio all setup properly

import os
import json
import base64
import azure.cognitiveservices.speech as speechsdk
from fastapi import FastAPI, WebSocket, Request, WebSocketDisconnect
from fastapi.responses import HTMLResponse, Response
from jinja2 import Template
from dotenv import load_dotenv
import requests


# Get our Azure credentials
load_dotenv()
SPEECH_KEY = os.environ.get("SPEECH_KEY")
SPEECH_REGION = os.environ.get("SPEECH_REGION")

# Some critical global variables
app = FastAPI()
wsserver = []

# Configure our Azure speech services
speech_config = speechsdk.SpeechConfig(subscription=SPEECH_KEY, region=SPEECH_REGION)

# Let's allow swearing to come through
speech_config.set_profanity(speechsdk.ProfanityOption.Raw)

audio_format = speechsdk.audio.AudioStreamFormat(samples_per_second=8000,
                                                    bits_per_sample=8,
                                                    channels=1, 
                                                    wave_stream_format=speechsdk.AudioStreamWaveFormat.MULAW)
stream = speechsdk.audio.PushAudioInputStream(stream_format=audio_format)
audio_config = speechsdk.audio.AudioConfig(stream=stream)

# instantiate the speech recognizer with push stream input
speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

def recognizing_cb(evt):
    print("RECOGNIZING: " + evt.result.text)

def recognized_cb(evt):
    print("RECOGNIZED: " + evt.result.text)

# Connect callbacks to the events fired by the speech recognizer
speech_recognizer.recognizing.connect(recognizing_cb)
speech_recognizer.recognized.connect(recognized_cb)
speech_recognizer.session_started.connect(lambda evt: print('SESSION STARTED: {}'.format(evt)))
speech_recognizer.session_stopped.connect(lambda evt: print('SESSION STOPPED {}'.format(evt)))
speech_recognizer.canceled.connect(lambda evt: print('CANCELED {}'.format(evt)))

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
#    global wsserver
    await websocket.accept()
    wsserver.append(websocket)
    try:
        while True:
            message = await websocket.receive_text()
            await on_message(websocket, message)

    except WebSocketDisconnect as e:
        print(f"WebSocket disconnected: {e}")

    finally:
        wsserver.remove(websocket)


async def on_message(websocket, message):
 #   global wsserver

    msg = json.loads(message)
    event = msg.get("event")

    if event == "connected":
        print("A new call has connected.")

    elif event == "start":
        print(f"Starting Media Stream {msg.get('streamSid')}")

        # start continuous speech recognition
        speech_recognizer.start_continuous_recognition()

    # The event that carries our audio stream
    elif event == "media":
        payload = msg['media']['payload']
        
        if payload:
            # Decode our payload and append to our array
            stream.write(base64.b64decode(payload))

    elif event == "stop":
        print("Call Has Ended")
        speech_recognizer.stop_continuous_recognition()

def get_ngrok_url():
    # Query ngrok API to get the tunnel information
    try:
        ngrok_tunnels = requests.get("http://127.0.0.1:4040/api/tunnels").json()

        for tunnel in ngrok_tunnels.get("tunnels", []):
            if tunnel.get("config", {}).get("addr") == "http://localhost:8080":
                # Return the public URL of the tunnel
                return tunnel.get("public_url")
    except requests.ConnectionError:
        print("Could not connect to ngrok API")
        return None
    

@app.post("/")
async def post(request: Request):
    host = request.client.host
    print("Post call - host=" + host)
    current_ngrok_url = get_ngrok_url()
    if current_ngrok_url:
        ws_url = current_ngrok_url.replace("http", "ws")
        xml = Template("""
        <Response>
            <Start>
                <Stream url="{{ ws_url }}/ws"/>
            </Start>
            <Say>Go time</Say>
            <Pause length="60" />
        </Response>
        """).render(ws_url=ws_url)
    else:
        # Fallback XML or error handling if ngrok URL is not available
        xml = """
        <Response>
            <Say>Error: ngrok URL not found</Say>
        </Response>
        """
    return Response(content=xml, media_type="text/xml")

if __name__ == "__main__":
    print("Listening at Port 8080")
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
