# Program to accept a phone call via Twilio and transcribe the audio. When the program detects the word "done",
# it tries to send up the contents of a binary file called "output.bin" on the websocket so you can hear it on the call.
# Need to have ngrok, FastAPI and Twilio all setup properly

import os
import re
import json
import base64
import time
from fastapi import FastAPI, WebSocket, Request, WebSocketDisconnect
from fastapi.responses import HTMLResponse, Response

import azure.cognitiveservices.speech as speechsdk
from twilio.twiml.voice_response import VoiceResponse, Connect

from rosie_utils import load_environment_variable
from voiceassistant import VoiceAssistant
from speechsynth_azure import SpeechSynthAzure

# Load all the required environment variables with proper error checking
SPEECH_KEY = load_environment_variable("SPEECH_KEY")
SPEECH_REGION = load_environment_variable("SPEECH_REGION")
SERVICE_PORT = load_environment_variable("SERVICE_PORT")
WEBSOCKET_STREAM_URL = load_environment_variable("WEBSOCKET_STREAM_URL")

# Some critical global variables
app = FastAPI()
wsserver = []
streamId = 0

start_time = time.time()
speech_synth = SpeechSynthAzure(SPEECH_KEY, SPEECH_REGION)

# instantiate the speech recognizer with push stream input
speech_recognizer = speech_synth.speech_recognizer()

time_to_respond = False

my_assistant = VoiceAssistant("gpt4")
assistant_text = None


def print_time_tracking(start_time, function_name):
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"TIMING: {function_name}  Execution time: {elapsed_time} seconds")

print_time_tracking(start_time, "Startup")

def remove_ending_period(s):
    # Check if the string ends with the word 'period'
    if s.endswith('period'):
        # Remove the last 6 characters ('period' and a space)
        return s[:-7]
    return s

def recognizing_cb(evt):
    global start_time
    print("RECOGNIZING: " + evt.result.text)


def recognized_cb(evt):
    global time_to_respond
    global my_assistant
    global assistant_text
    global start_time

    start_time = start_time = time.time()
    txt = evt.result.text
    if not txt:
        print("RECOGNIZED: None ---- ENDING")
        return
    
    print("RECOGNIZED: " + txt)
    
    # My edits - start translating as soon as there is a pause

    my_assistant.next_user_response(txt)
    print_time_tracking(start_time, "Next_user:")
    
    my_assistant.print_thread()
    print("-----------------------------------")
    start_time = start_time = time.time()
    assistant_text = my_assistant.next_assistant_response()
    print_time_tracking(start_time, "Next_Assistant")
 
    print("RESPONSE:", assistant_text)
    my_assistant.print_thread()
    print("-----------------------------------")
    time_to_respond = True
    

# This function gets called when we are trying to send some media data inbound on the phone call
# This is trigged by the word "done" in the audio of the message
async def send_response(websocket: WebSocket):
    global time_to_respond
    global assistant_text
    global speech_synth


    #print("Responding to Twilio")
    time_to_respond = False

    seq = 1

    if not assistant_text: 
        print("Not assistant_text")
        return
    try:
        synth_text = assistant_text
        #print("Txt to convert to speech", assistant_text)
        start_time = start_time = time.time()
        encoded_data = speech_synth.generate_speech(synth_text)
        print_time_tracking(start_time, "generate speech")

        # seq = seq + 1;
        # Send the encoded data over the WebSocket stream
        start_time = start_time = time.time()
        #print("Sending Media Message: ")
        await websocket.send_json(media_data(encoded_data, streamId, seq))
        markdata = mark_data(streamId)
        #print("Sending Mark Message: ", markdata)
        await websocket.send_json(markdata)
        print_time_tracking(start_time, "Streaming AI Voice")
        speech_synth.cleanup()
        
    except Exception as e:
        print(f"Error: {e}")

          
# Connect callbacks to the events fired by the speech recognizer
speech_recognizer.recognizing.connect(recognizing_cb)
speech_recognizer.recognized.connect(recognized_cb)
speech_recognizer.session_started.connect(lambda evt: print('SESSION STARTED: {}'.format(evt)))
speech_recognizer.session_stopped.connect(lambda evt: print('SESSION STOPPED {}'.format(evt)))
speech_recognizer.canceled.connect(lambda evt: print('CANCELED {}'.format(evt)))

def media_data(encoded_data, streamId, seq):
    return {
            "event": "media",
            "streamSid": streamId,
        #    "sequenceNumber": seq,     # Including a sequence in it throws back a Warning 31951 error
            "media": {
                "payload": encoded_data
            }
    }

def mark_data(streamId):
    return { 
                "event": "mark",
                "streamSid": streamId,
                "mark": {
                    "name": "inbound"
                }
            }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    wsserver.append(websocket)
    try:
        while True:
            message = await websocket.receive_text()
            await on_message(websocket, message)
            if time_to_respond:
                await send_response(websocket)

    except WebSocketDisconnect as e:
        print(f"WebSocket disconnected: {e}")

    finally:
        wsserver.remove(websocket)


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

    response = VoiceResponse()
    response.say('Please respond as a restaurant receptionist receiving an inbound phone call.')
    connect = Connect()
    connect.stream(
        name='Outbound',
        url = WEBSOCKET_STREAM_URL
    )
    response.append(connect)
    response.pause(length=15)
    return Response(content=response.to_xml(), media_type="text/xml")


if __name__ == "__main__":
    print("Listening at Port ", SERVICE_PORT)
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=SERVICE_PORT)
