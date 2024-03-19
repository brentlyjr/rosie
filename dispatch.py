# Main dispatch controller for our Rosie Voice Assistance

import json
import uvicorn
import threading
import time
from fastapi import FastAPI, WebSocket, Request, WebSocketDisconnect
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from twilio.twiml.voice_response import VoiceResponse, Connect
from rosie_utils import load_environment_variable, Profiler, get_ngrok_ws_url, get_ngrok_http_url
from callmanager import OutboundCall, CallManager
from voiceassistant import VoiceAssistant
from speechsynth_azure import SpeechSynthAzure
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from live_stream import LiveAudioStreamManager

# Load all the required environment variables with proper error checking
SPEECH_KEY = load_environment_variable("AZURE_SPEECH_KEY")
SPEECH_REGION = load_environment_variable("AZURE_SPEECH_REGION")
SERVICE_PORT = load_environment_variable("SERVICE_PORT")

# Some critical global variables
app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Our global profiler to give us overall timing of various components
profiler = Profiler()
counter= 0

# Instantiate our global call manager to track all concurrenet calls
rosieCallManager = CallManager()
liveAudioStreamManager = LiveAudioStreamManager(rosieCallManager)

# This CORS middleware is needed to allow cross-site domains. Without it, we are not allowed
# to receive https calls from domains other than the ones we are running our server on
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow requests from all origins (replace with specific origins if needed)
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],  # Allow specific HTTP methods
    allow_headers=["*"],  # Allow all headers (replace with specific headers if needed)
    allow_credentials=True,  # Allow credentials (cookies, authorization headers)
    expose_headers=["Content-Length", "X-Total-Count"],  # Expose additional headers
    max_age=600,  # Cache preflight response for 10 minutes
)


# TODO: Make a variable for GPT-4 and downgrade when testing to save money!


def recognizing_cb(evt, call_sid):
    global profiler
    global counter
    counter =0

    call_obj = rosieCallManager.get_call(call_sid)
    
    print("LISTENING: " + evt.result.text)
    if not call_obj.get_start_recognition():
        profiler.update("Listening")
        call_obj.set_start_recognition(True)
    profiler.print("In recognizing")


def recognized_cb(evt, call_sid):
    global profiler

    call_obj = rosieCallManager.get_call(call_sid)
    assistant = call_obj.get_voice_assistant()

    profiler.update("Recognized")
    call_obj.set_start_recognition(False)
    txt = evt.result.text
    if not txt:
        print("RECOGNIZED: None ---- ENDING")
        return
    
    print("RECOGNIZED: " + txt)
    profiler.print("Recognized")

    # My edits - start translating as soon as there is a pause

    assistant.next_user_response(txt)   
    assistant.print_thread()
    print("-----------------------------------")
    profiler.update("ChatGPT-Full")
    profiler.update("ChatGPT-chunk")
    assistant.next_assistant_response()
    profiler.print("Next_Assistant")
    print("-----------------------------------")
    # We now tell our call object it is time to respond back to the user
    call_obj.set_respond_time(True)
    

# This function gets called when we are trying to send some media data inbound on the phone call
async def send_response(websocket: WebSocket, call_sid: str):
    global profiler

    call_obj = rosieCallManager.get_call(call_sid)
    assistant = call_obj.get_voice_assistant()
    speech_synth = call_obj.get_synthesizer()
    stream_id = call_obj.get_stream_id()

    print("Responding to Twilio")
    call_obj.set_respond_time(False)

    try:
        for synth_text in assistant.next_chunk():
            profiler.print("Chat chunk")
            profiler.update("ChatGPT-chunk")
            print("Txt to convert to speech: ", synth_text)
            profiler.update("SpeechSynth")
            digit_presses = assistant.find_press_digits(synth_text)
            profiler.print("Generate speech")
            #digit_presses = "1234567890"
            if digit_presses:
                for digit in digit_presses:
                    encoded_data = speech_synth.play_digit(int(digit))
                    await websocket.send_json(media_data(encoded_data, stream_id))
            else:
                encoded_data = speech_synth.generate_speech(synth_text)
                await websocket.send_json(media_data(encoded_data, stream_id))
            
            profiler.print("Streaming AI Voice")
            speech_synth.cleanup()
        
        profiler.print("ChatGPT Done")

        if assistant.conversation_ended():
            pause_time = speech_synth.time_to_speak(assistant.last_message_text())
            time.sleep(pause_time)
            call_obj.hang_up()
            assistant.summarize_conversation()

    except Exception as e:
        print(f"Error: {e}")

def media_data(encoded_data, streamId):
    return {
            "event": "media",
            "streamSid": streamId,
            "media": {
                "payload": encoded_data
            }
    }

async def on_message(websocket, message, call_sid):
    msg = json.loads(message)
    event = msg.get("event")
    global counter

    if event == "connected":
        print("A new stream has connected for call:", call_sid)

    elif event == "start":
        stream_id = msg.get('streamSid')
        print(f"Starting Media Stream {stream_id}")

        # Because we are starting off our streams, let's instantiate the speech_synth and
        #  the speech_recognizer for this call
        speech_synth = SpeechSynthAzure(SPEECH_KEY, SPEECH_REGION, call_sid)
        speech_recognizer = speech_synth.speech_recognizer()

        # And finally initialize our rosie voice assistant with LLM and call id
        assistant = VoiceAssistant("gpt4", call_sid)

        # And store these with our call so we can retrieve them later
        call_obj = rosieCallManager.get_call(call_sid)
        call_obj.set_synthesizer(speech_synth)
        call_obj.set_recognizer(speech_recognizer)
        call_obj.set_stream_id(stream_id)
        call_obj.set_voice_assistant(assistant)

        # Now instantiate our callbacks for these streams
        speech_recognizer.recognizing.connect(lambda evt: recognizing_cb(evt, call_sid))
        speech_recognizer.recognized.connect(lambda evt: recognized_cb(evt, call_sid))
        speech_recognizer.session_started.connect(lambda evt: print('SESSION STARTED: {}'.format(evt)))
        speech_recognizer.session_stopped.connect(lambda evt: print('SESSION STOPPED {}'.format(evt)))
        speech_recognizer.canceled.connect(lambda evt: print('CANCELED {}'.format(evt)))

        # Start continuous speech recognition
        speech_recognizer.start_continuous_recognition()
        profiler.update('azuredone')


    # The event that carries our audio stream
    elif event == "media": 
        payload = msg['media']['payload']
        counter +=1
#        print(f"In media{counter}")
        if payload:
            call_obj = rosieCallManager.get_call(call_sid)
            speech_synth = call_obj.get_synthesizer()
            speech_synth.write_stream(payload)
 
    elif event == "stop":
        print("Call Has Ended")
        call_obj = rosieCallManager.get_call(call_sid)
        call_obj.set_call_ending(True)


# This in our main clean-up API. This will get triggered when the call automatically is hung up
# through our twilio APIs or when the call has received a termination from the other side of the web socket
def cleanup_call(call_sid):
    print("Cleaning up call resources")
    call_obj = rosieCallManager.get_call(call_sid)
    call_obj.get_recognizer().stop_continuous_recognition()
    call_obj.get_synthesizer().stop_recording()
    liveAudioStreamManager.stop_stream(call_sid)
    # Logic to close out the call by setting the duration and saving the history out
    timediff = time.time() - call_obj.get_start_time()
    call_obj.set_duration(timediff)
    print("Call had duration of " + str(call_obj.get_duration()) + " seconds.")

    # Save the history of our object to our database
    rosieCallManager.save_history(call_obj)



# This is our main websocket controller. This is what we will use to collect and send both
# inbound and outbound audio streams over our voice API. Each call will be assigned a unique
# websocket URL of the structure /ws/call_sid. This allows us to have multiple calls going
# simultaneously. We will lookup that specific calls data from our global CallManager so we
# can properly operate on each one independently.
@app.websocket("/ws/{call_sid}")
async def websocket_endpoint(websocket: WebSocket, call_sid: str):
    await websocket.accept()
    try:
        while True:
            # Get our websocket message
            message = await websocket.receive_text()
            await on_message(websocket, message, call_sid)
            call_obj = rosieCallManager.get_call(call_sid)
            # Detect when it is time to now respond on this websocket
            if call_obj.get_respond_time():
                await send_response(websocket, call_sid)
            # Detect when our call has ended and we need to cleanup resources
            if call_obj.get_call_ending():
                cleanup_call(call_sid)
                # We have finished our call and no longer need to loop in this websocket thread
                break

    except WebSocketDisconnect as e:
        print(f"WebSocket disconnected: {e}")


# This is a standard http GET call to the top level of our main web server. This is where we will
# just return the front web page for Rosie to manage the voice assistant.
@app.get("/", response_class=HTMLResponse)
async def toplevel(request: Request):
    # Get our server URL
    server_url = get_ngrok_http_url()

    # Insert that URL into our template and return
    data = {"server_url": server_url}
    return templates.TemplateResponse("rosie.html", {"request": request, "data": data})


@app.post("/api/callback")
async def callback(request: Request):
    global profiler
    print("Twilio Main Callback - host=" + request.client.host)

    # Get our key variables from the callback. basically SID, and other details about the call
    form = await request.form()
    call_sid = form.get('CallSid', None)
    to_number = form.get('To', None)
    from_number = form.get('From', None)

    # We will assume this is a call until we lookup the SID and find out if it already exists
    inbound_call = False

    # Lookup whether we have a call already estabished.
    call_obj = rosieCallManager.get_call(call_sid)

    # If we don't have a call object, this means it is an incoming call to our server, so establish a new
    # call object for this session and attach to our global call manager
    if call_obj == None:
        call_obj = OutboundCall(to_number, from_number, call_sid)
        rosieCallManager.add_call(call_sid, call_obj)
        inbound_call = True

    # Make this as the starttime for our call
    call_obj.set_start_time()

    # Build a response back to the twilio server that explains how to handle the outbound stream
    # for this voice call
    ws_url = get_ngrok_ws_url() + '/' + call_sid
    response = VoiceResponse()
    print("Using websocket " + ws_url + " for this call.")
    profiler.print("Websocket begin")

    # If we are calling out, don't provide this message as it doesn't make sense
    if inbound_call == True:
        response.say('Please respond as a restaurant receptionist receiving an inbound phone call.')

    # Connect to the call and start an outbound websocket stream
    connect = Connect()
    connect.stream(
        name='Outbound',
        url = ws_url
    )
    response.append(connect)
    profiler.print("Websocket connect")
    return Response(content=response.to_xml(), media_type="text/xml")


# This callback will be configured to be invoked when we are initiating an outbound call. We are asking to
# receive all possible events which are: initiated, ringing, in-progress, completed. Right now we are just
# monitoring these statuses, and using it to time the length of the call.
@app.post("/api/callstatus")
async def callstatus(request: Request):
    global profiler
    print("Twilio CallStatus Callback - host=" + request.client.host)

    # Get our key variables from the callback. basically our call SID and status
    form = await request.form()
    call_sid = form.get('CallSid', None)
    status = form.get('CallStatus', None)

    # Lookup our current call from the call manager and updates status
    call_obj = rosieCallManager.get_call(call_sid)
    call_obj.set_status(status)

    '''
    # Taking this code out from here because inbound calls do not get call status events. Ideally this is
    # where the logic is to set start and end call events, but for now we will just keep them in other
    # places where we can manually detect these events.
    if status == 'initiated':
        call_obj.set_start_time(datetime.now())
    '''
    if status == 'in-progress':
        profiler.update('connected')
        profiler.print("Connected")

    print("Call SID:", call_sid, "has status:", status)
    if status == 'completed':
        rosieCallManager.remove_call(call_sid)

    '''
    # Taking this out for now because an inbound call does not get callstatus events. This is probably
    # the right place to do it long term, but for now, we will move the duration calculation and the
    # history saving to when we are in 'sendresponse' and detect the end of the conversation
    if status == 'completed':
        timediff = time.time() - call_obj.get_start_time()
        call_obj.set_duration(timediff)
        print("Call had duration of " + str(call_obj.get_duration()) + " seconds.")

        # Save the history of our object to our database
        rosieCallManager.save_history(call_obj)
    '''


# Rest API call for Rosie that will instantiate an outbound call. This request is expecting a JSON string
# that has a TO_NUMBER and a FROM_NUMBER as its input.
@app.post("/api/makecall")
async def makecall(request: Request):
    profiler.reset()
    profiler.update("Make call")
    # Parse JSON request body for this call
    request_body = await request.json()
    
    call_obj = OutboundCall.from_string(request_body)
    callId = call_obj.make_call()
    rosieCallManager.add_call(call_obj.get_call_sid(), call_obj)
    profiler.print("Call started")
    return {f"message": "Making outbound call to: {call.get_to_number()} from: {call.get_from_number()}"}


# Rest API call that returns all the call results stored in our local history
@app.get("/api/getallcalls")
async def getallcalls(request: Request):
    active_calls = rosieCallManager.get_active_calls()
    for call in active_calls:
        call['active']=True
    history_data = rosieCallManager.get_history()
    for call in history_data:
        call['active']=False
    return active_calls + history_data


@app.get("/api/gethistory")
async def gethistory(request: Request):
    history_data = rosieCallManager.get_history()
    return history_data

@app.get("/api/getactivecalls")
async def getactivecalls(request: Request):
    active_calls = rosieCallManager.get_active_calls()
    return active_calls

# Rest API to retrieve an audio file for a specific call and stream it back to the client
@app.get("/api/getaudiofile")
async def getaudiofile(request: Request):
    query_params = request.query_params
    call_sid = query_params.get('CallSid', None)
    if call_sid == None:
        return Response(status_code=404, content="Invalid CallSid")

    sound_stream = rosieCallManager.get_saved_audio_stream(call_sid)
    if sound_stream == None:
        return Response(status_code=404, content="Audio file not found")

    return StreamingResponse(sound_stream, media_type="audio/wav")

@app.get("/api/endcall")
async def endcall(request: Request):
    query_params = request.query_params
    call_sid = query_params.get('CallSid', None)
    if call_sid == None:
        return Response(status_code=404, content="Invalid CallSid")
    call_obj = rosieCallManager.get_call(call_sid)
    liveAudioStreamManager.stop_stream(call_sid)
    call_obj.set_call_ending(True)
    return {f"message": "Ending call: {call_sid}"}


@app.get("/api/stream-live-audio")
async def stream_live_audio_endpoint(request: Request):
    #global live_audio_streams
    query_params = request.query_params
    action = query_params.get('action', None)
    call_sid = query_params.get('CallSid', None)
    if call_sid == None:
        return Response(status_code=404, content="Invalid CallSid")
    if action == 'start':    
        print(f"Starting audio stream {call_sid}")
        return StreamingResponse(liveAudioStreamManager.play_stream(call_sid), media_type="audio/wav")
    elif action == 'stop':
         print(f"Stopping audio stream {call_sid}")
         liveAudioStreamManager.stop_stream(call_sid)

# For Debugging Purposes
@app.get("/audio-microphone")
async def audio_microphone():
    print("Inside mic audio")
    return StreamingResponse(liveAudioStreamManager.stream_microphone(), media_type="audio/wav")

# For Debugging Purposes
@app.get("/audio-file")
async def audio_microphone():
    print("Inside file audio")
    active_calls = rosieCallManager.get_active_calls()
    call_sid = active_calls[0]['sid']
    return StreamingResponse(liveAudioStreamManager.play_stream(call_sid), media_type="audio/wav")

# For Debugging Purposes
@app.get("/stop-stream")
async def audio_microphone(request: Request):
    print("Stopping stream")
    active_calls = rosieCallManager.get_active_calls()
    call_sid = active_calls[0]['sid']
    liveAudioStreamManager.stop_stream(call_sid)


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