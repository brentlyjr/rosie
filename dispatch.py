# Main dispatch controller for our Rosie Voice Assistance

import os
import re
import json
import base64
import time
from fastapi import FastAPI, WebSocket, Request, WebSocketDisconnect
from fastapi.responses import HTMLResponse, Response
import azure.cognitiveservices.speech as speechsdk
from twilio.twiml.voice_response import VoiceResponse, Connect
from rosie_utils import load_environment_variable, Profiler, get_ngrok_url
from voiceassistant import VoiceAssistant
from speechsynth_azure import SpeechSynthAzure

# Load all the required environment variables with proper error checking
SPEECH_KEY = load_environment_variable("SPEECH_KEY")
SPEECH_REGION = load_environment_variable("SPEECH_REGION")
SERVICE_PORT = load_environment_variable("SERVICE_PORT")

# Some critical global variables
app = FastAPI()
streamId = 0

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



@app.post("/")
async def post(request: Request):
    host = request.client.host
    print("Post call - host=" + host)
    ws_url = get_ngrok_url()

    response = VoiceResponse()
    response.say('Please respond as a restaurant receptionist receiving an inbound phone call.')
    connect = Connect()
    connect.stream(
        name='Outbound',
        url = ws_url
    )
    response.append(connect)
    response.pause(length=15)
    return Response(content=response.to_xml(), media_type="text/xml")


if __name__ == "__main__":
    print("Listening at Port ", SERVICE_PORT)
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(SERVICE_PORT))
