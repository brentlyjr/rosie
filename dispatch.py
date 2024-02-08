# Main dispatch controller for our Rosie Voice Assistance

import os
import re
import json
import base64
import time
import uvicorn
import threading
from fastapi import FastAPI, WebSocket, Request, WebSocketDisconnect
from fastapi.responses import HTMLResponse, Response
import azure.cognitiveservices.speech as speechsdk
from twilio.twiml.voice_response import VoiceResponse, Connect
from rosie_utils import load_environment_variable, Profiler, get_ngrok_ws_url, get_ngrok_http_url, OutboundCall
from voiceassistant import VoiceAssistant
from speechsynth_azure import SpeechSynthAzure
from twilio.rest import Client
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates


# Load all the required environment variables with proper error checking
SPEECH_KEY = load_environment_variable("AZURE_SPEECH_KEY")
SPEECH_REGION = load_environment_variable("AZURE_SPEECH_REGION")
SERVICE_PORT = load_environment_variable("SERVICE_PORT")
TWILIO_ACCOUNT_SID = load_environment_variable("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = load_environment_variable("TWILIO_AUTH_TOKEN")

# Some critical global variables
app = FastAPI()
templates = Jinja2Templates(directory="templates")
streamId = 0

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow requests from all origins (replace with specific origins if needed)
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],  # Allow specific HTTP methods
    allow_headers=["*"],  # Allow all headers (replace with specific headers if needed)
    allow_credentials=True,  # Allow credentials (cookies, authorization headers)
    expose_headers=["Content-Length", "X-Total-Count"],  # Expose additional headers
    max_age=600,  # Cache preflight response for 10 minutes
)


# Determine if Rosie should call out to a preferred number
config = OutboundCall()
profiler = Profiler()
speech_synth = SpeechSynthAzure(SPEECH_KEY, SPEECH_REGION)

# instantiate the speech recognizer with push stream input
speech_recognizer = speech_synth.speech_recognizer()

time_to_respond = False

my_assistant = VoiceAssistant("gpt4")
start_recognition = False


def recognizing_cb(evt):
    global profiler
    global start_recognition

    print("LISTENING: " + evt.result.text)
    if not start_recognition:
        profiler.update("Listening")
        start_recognition = True


def recognized_cb(evt):
    global profiler
    global start_recognition
    global my_assistant
    global time_to_respond 
   
    profiler.update("Recognized")
    start_recognition = False
    txt = evt.result.text
    if not txt:
        print("RECOGNIZED: None ---- ENDING")
        return
    
    print("RECOGNIZED: " + txt)
    profiler.print("Recognized")

    # My edits - start translating as soon as there is a pause

    my_assistant.next_user_response(txt)   
    my_assistant.print_thread()
    print("-----------------------------------")
    profiler.update("ChatGPT-Full")
    profiler.update("ChatGPT-chunk")
    my_assistant.next_assistant_response()
    profiler.print("Next_Assistant")
    print("-----------------------------------")
    time_to_respond = True
    

# This function gets called when we are trying to send some media data inbound on the phone call

async def send_response(websocket: WebSocket):
    global time_to_respond
    global speech_synth
    global my_assistant
    global profiler

    print("Responding to Twilio")
    time_to_respond = False

    try:
        for synth_text in my_assistant.next_chunk():
            profiler.print("Chat chunk")
            profiler.update("ChatGPT-chunk")
            print("Txt to convert to speech: ", synth_text)
            profiler.update("SpeechSynth")
            encoded_data = speech_synth.generate_speech(synth_text)
            profiler.print("Generate speech")

            # Send the encoded data over the WebSocket stream
            #print("Sending Media Message: ")
            await websocket.send_json(media_data(encoded_data, streamId))
            profiler.print("Streaming AI Voice")
            speech_synth.cleanup()

        profiler.print("ChatGPT Done")
        if my_assistant.conversation_ended():
            my_assistant.summarize_conversation()

    except Exception as e:
        print(f"Error: {e}")

          
# Connect callbacks to the events fired by the speech recognizer
speech_recognizer.recognizing.connect(recognizing_cb)
speech_recognizer.recognized.connect(recognized_cb)
speech_recognizer.session_started.connect(lambda evt: print('SESSION STARTED: {}'.format(evt)))
speech_recognizer.session_stopped.connect(lambda evt: print('SESSION STOPPED {}'.format(evt)))
speech_recognizer.canceled.connect(lambda evt: print('CANCELED {}'.format(evt)))

def media_data(encoded_data, streamId):
    return {
            "event": "media",
            "streamSid": streamId,
            "media": {
                "payload": encoded_data
            }
    }

async def on_message(websocket, message):
    global streamId
    global my_assistant
    global speech_synth

    msg = json.loads(message)
    event = msg.get("event")

    if event == "connected":
        print("A new call has connected.")

    elif event == "start":
        streamId = msg.get('streamSid')
        print(f"Starting Media Stream {streamId}")

        # start continuous speech recognition
        speech_recognizer.start_continuous_recognition()

    # The event that carries our audio stream
    elif event == "media":
        payload = msg['media']['payload']
        
        if payload:
            speech_synth.write_stream(payload)
 
    elif event == "stop":
        print("Call Has Ended")
        speech_recognizer.stop_continuous_recognition()
        my_assistant = VoiceAssistant('gpt-4')


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            message = await websocket.receive_text()
            await on_message(websocket, message)
            if time_to_respond:
                await send_response(websocket)

    except WebSocketDisconnect as e:
        print(f"WebSocket disconnected: {e}")


@app.get("/", response_class=HTMLResponse)
async def get(request: Request):
    server_url = get_ngrok_http_url()
    data = {"server_url": server_url}
    return templates.TemplateResponse("rosie.html", {"request": request, "data": data})


@app.post("/")
async def post(request: Request):
    host = request.client.host
    print("Post call - host=" + host)
    ws_url = get_ngrok_ws_url()

    response = VoiceResponse()
    # If we are calling out, don't provide this message as it doesn't make sense
    if config.call_out == False:
        response.say('Please respond as a restaurant receptionist receiving an inbound phone call.')
    connect = Connect()
    connect.stream(
        name='Outbound',
        url = ws_url
    )
    response.append(connect)
    response.pause(length=15)
    return Response(content=response.to_xml(), media_type="text/xml")


@app.post("/api")
async def get_api(request: Request):
    print("in api call")
    return {"message": "Results received successfully"}  # Placeholder response, replace as needed


# Function to instantiate our web server
def run_fastapi():
    print("Listening at Port ", SERVICE_PORT)
    uvicorn.run(app, host="0.0.0.0", port=int(SERVICE_PORT))


# This check just ensures we are executing from a command line and not as a library file
if __name__ == "__main__":
    # Create a thread for FastAPI
    fastapi_thread = threading.Thread(target=run_fastapi)

    # Start the FastAPI thread in the background
    fastapi_thread.start()

    if config.call_out:
        print("Starting our outbound call")
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

        call = client.calls.create(
                            method='POST',
                            status_callback=get_ngrok_http_url(),
                            status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
                            status_callback_method='POST',
                            url=get_ngrok_http_url(),
                            to=config.to_number,
                            from_=config.from_number
                        )

        print(call.sid)
