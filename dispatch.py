# Main dispatch controller for our Rosie Voice Assistance

import json
import uvicorn
import threading
import time
import base64
from fastapi import FastAPI, WebSocket, Request, WebSocketDisconnect
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from twilio.twiml.voice_response import VoiceResponse, Connect
from rosie_utils import load_config, load_environment_variable, get_ngrok_ws_url, get_ngrok_http_url
from callmanager import OutboundCall, rosieCallManager
from voiceassistant import VoiceAssistant
from speechsynth_azure import SynthesizerManager
from speechrecognizer_azure import SpeechRecognizerAzure
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

# Instantiate our global call manager to track all concurrenet calls
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

def media_data(encoded_data, streamId):
    return {
            "event": "media",
            "streamSid": streamId,
            "media": {
                "payload": encoded_data
            }
    }

# This is our main loop when reading messages off the incoming phone stream. We read a websocket
# message and then this is the loop that processes the message based on the type of message it is
async def on_message(websocket, message, call_sid):
    msg = json.loads(message)
    event = msg.get("event")
    global counter

    if event == "connected":
        print("A new stream has connected for call:", call_sid)

    elif event == "start":
        stream_id = msg.get('streamSid')
        print(f"Starting Media Stream {stream_id}")

        # Because we are starting off our streams, let's instantiate the synthesizer manager and
        #  the speech_recognizer for this call

        # get Speech Synth details from the config.ini file - provider and voice
        # synth_config = load_config('Synth')
        # speech_synth = get_speech_synth_service(synth_config['provider'], call_sid, voice=synth_config['voice'])
        synth_manager = SynthesizerManager(SPEECH_KEY, SPEECH_REGION, call_sid)
        speech_recognizer = SpeechRecognizerAzure(SPEECH_KEY, SPEECH_REGION, call_sid)

        # And store these with our call so we can retrieve them later
        call = rosieCallManager.get_call(call_sid)
        call.set_synthesizer_manager(synth_manager)
        call.set_recognizer(speech_recognizer)
        call.set_stream_id(stream_id)

        # Start continuous speech recognition
        speech_recognizer.start_recognition()

    # The event that carries our audio stream
    elif event == "media": 
        payload = msg['media']['payload']
        call = rosieCallManager.get_call(call_sid)

        # If Rosie is not talking, send all of our incoming phone messages that we are
        # receiving on the phone call to our audio buffer
        if call.get_respond_time() == False:
            call.save_audio_to_call_buffer(base64.b64decode(payload))

        # If we have some incoming data from the phone line that we need to recognize
        if payload:
            speech_recognizer = call.get_recognizer()
            speech_recognizer.write_stream(payload)
 
    elif event == "stop":
        print("Call Has Ended")
        call = rosieCallManager.get_call(call_sid)
        call.set_call_ending(True)


# This in our main clean-up API. This will get triggered when the call automatically is hung up
# through our twilio APIs or when the call has received a termination from the other side of the web socket
def cleanup_call(call_sid):
    print("Cleaning up call resources")
    call = rosieCallManager.get_call(call_sid)
    speech_recognizer = call.get_recognizer()
    speech_recognizer.stop_recognition()

    liveAudioStreamManager.stop_stream(call_sid)
    # Logic to close out the call by setting the duration and saving the history out
    timediff = time.time() - call.get_start_time()
    call.set_duration(timediff)
    print("Call had duration of " + str(call.get_duration()) + " seconds.")

    # Save the history of our object to our database
    rosieCallManager.save_history(call)
    # We don't need to save this out as we are creating it along the way
    # call.save_audio_recording()


# This is our main websocket controller. This is what we will use to collect and send both
# inbound and outbound audio streams over our voice API. Each call will be assigned a unique
# websocket URL of the structure /ws/call_sid. This allows us to have multiple calls going
# simultaneously. We will lookup that specific calls data from our global CallManager so we
# can properly operate on each one independently.
@app.websocket("/ws/{call_sid}")
async def websocket_endpoint(websocket: WebSocket, call_sid: str):
    # Negotiate and setup our websocket connection 
    await websocket.accept()

    # We will keep the call ongoing until
    final_conversation_segment = False

    try:
        while True:
            # Get our incoming websocket message and process it
            message = await websocket.receive_text()
            await on_message(websocket, message, call_sid)

            # New code for processing and synthesizing text
            call = rosieCallManager.get_call(call_sid)
            synth_manager = call.get_synthesizer_manager()

            # Ideally we don't need this. But our stream is not initialized in here until after we start. We should just
            # be able to check if there is a response and either skip or process
            if call.get_respond_time():

                # Fetch our assistant and synthesizer manager
                assistant = call.get_voice_assistant()

                # Append any new chunks of response text into our queue for synthesizing
                for synth_text, status in assistant.next_chunk():

                    # Only gets into this loop when we have another chunk of data back from ChatGPT
                    synth_manager.synthesize_speech(synth_text, status)
                    if status == 2:
                        final_conversation_segment = True
                        timer_start_time = time.time()
                        pause_time = synth_manager.time_to_speak(assistant.last_message_text())
                        print("End of conversation detected - starting timer for ", pause_time, " seconds to get last voice synthesis")

                digit_presses = assistant.find_press_digits(synth_text)
                if digit_presses:
                    for digit in digit_presses:
                        encoded_data = synth_manager.play_digit(int(digit))
                        await websocket.send_json(media_data(encoded_data, stream_id))

                # I guess we are done getting data from ChatGPT here. This really should not be blocking
                call.set_respond_time(False)

            # Even if we are not in respond time, we may have some data to send if our synthesis is still running
            # But the first couple times through here, we have not initialized all our objects until we get our
            # first 'start' media message
            if synth_manager:
                raw_ulaw_data, status = synth_manager.get_more_synthesized_data()
                if raw_ulaw_data:
                    stream_id = call.get_stream_id()
                    encoded_data = base64.b64encode(raw_ulaw_data).decode('utf-8')
                    await websocket.send_json(media_data(encoded_data, stream_id))

            # We get to this case when we have detected a "hang-up" word token in our spoken text
            # We are not done synthesizing, so we need to wait for the remainder of the synthesis
            # to finish
            if final_conversation_segment == True:
                delay = time.time() - timer_start_time
                if delay > pause_time:
                    assistant.summarize_conversation()
                    call.hang_up()

            # Detect when our call has ended and we need to cleanup resources
            if call.get_call_ending():
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
    print("Twilio Main Callback - host=" + request.client.host)

    # Get our key variables from the callback. basically SID, and other details about the call
    form = await request.form()
    call_sid = form.get('CallSid', None)
    to_number = form.get('To', None)
    from_number = form.get('From', None)

    # We will assume this is a call until we lookup the SID and find out if it already exists
    inbound_call = False

    # Lookup whether we have a call already estabished.
    call = rosieCallManager.get_call(call_sid)

    # If we don't have a call object, this means it is an incoming call to our server, so establish a new
    # call object for this session and attach to our global call manager
    if call == None:
        call = OutboundCall(to_number, from_number, call_sid)

        # Setup a Rosie voice assistant for this call with LLM and call id
        assistant = VoiceAssistant()

        # And load the system propmt so our call will execute with all the right details
        assistant.load_system_prompt()
        call.set_voice_assistant(assistant)

        # Put this call in our active call queue for tracking
        rosieCallManager.add_call(call_sid, call)

        # Mark this as an inbound call
        inbound_call = True

    # Make this as the starttime for our call
    call.set_start_time()

    # Build a response back to the twilio server that explains how to handle the outbound stream
    # for this voice call
    ws_url = get_ngrok_ws_url() + '/' + call_sid
    response = VoiceResponse()
    print("Using websocket " + ws_url + " for this call.")

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
    return Response(content=response.to_xml(), media_type="text/xml")


# This callback will be configured to be invoked when we are initiating an outbound call. We are asking to
# receive all possible events which are: initiated, ringing, in-progress, completed. Right now we are just
# monitoring these statuses, and using it to time the length of the call.
@app.post("/api/callstatus")
async def callstatus(request: Request):
    print("Twilio CallStatus Callback - host=" + request.client.host)

    # Get our key variables from the callback. basically our call SID and status
    form = await request.form()
    call_sid = form.get('CallSid', None)
    status = form.get('CallStatus', None)

    # Lookup our current call from the call manager and updates status
    call = rosieCallManager.get_call(call_sid)
    call.set_status(status)

    '''
    # Taking this code out from here because inbound calls do not get call status events. Ideally this is
    # where the logic is to set start and end call events, but for now we will just keep them in other
    # places where we can manually detect these events.
    if status == 'initiated':
        call.set_start_time(datetime.now())
    '''
    if status == 'in-progress':
        pass

    print("Call SID:", call_sid, "has status:", status)
    if status == 'completed':
        rosieCallManager.remove_call(call_sid)

    '''
    # Taking this out for now because an inbound call does not get callstatus events. This is probably
    # the right place to do it long term, but for now, we will move the duration calculation and the
    # history saving to when we are in 'sendresponse' and detect the end of the conversation
    if status == 'completed':
        timediff = time.time() - call.get_start_time()
        call.set_duration(timediff)
        print("Call had duration of " + str(call.get_duration()) + " seconds.")

        # Save the history of our object to our database
        rosieCallManager.save_history(call)
    '''


# Rest API call for Rosie that will instantiate an outbound call. This request is expecting a JSON string
# that has a TO_NUMBER and a FROM_NUMBER as its input.
@app.post("/api/makecall")
async def makecall(request: Request):
    # Parse JSON request body for this call
    request_body = await request.json()

    # Extract our variables
    toNumber = request_body.get('TO_NUMBER', None)
    fromNumber = request_body.get('FROM_NUMBER', None)

    # Initiate a new call object for this call we are starting
    call = OutboundCall(toNumber, fromNumber)

    del request_body['TO_NUMBER']
    del request_body['FROM_NUMBER']

    #request_body['TEMPLATE'] = 'doctor'

    # Setup a Rosie voice assistant for this call with LLM and call id
    llm_config = load_config('LLM')   
    assistant = VoiceAssistant(llm_config['model'],request_body)
    call.set_voice_assistant(assistant)

    # Start the outbound call process
    call_sid = call.make_call()

    # Add this to our queue of "live" outbound calls
    rosieCallManager.add_call(call_sid, call)

    return {"message": "Making outbound call to: {toNumber} from: {fromNumber}"}


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
    global rosieCallManager

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
    call = rosieCallManager.get_call(call_sid)
    liveAudioStreamManager.stop_stream(call_sid)
#    call.set_call_ending(True)
    call.hang_up()
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
async def stream_live_file():
    print("Inside file audio")
    active_calls = rosieCallManager.get_active_calls()
    if active_calls[0]:
        call_sid = active_calls[0]['sid']
        return StreamingResponse(liveAudioStreamManager.play_stream(call_sid), media_type="audio/wav")

# For Debugging Purposes
@app.get("/stop-stream")
async def stop_live_file(request: Request):
    print("Stopping stream")
    active_calls = rosieCallManager.get_active_calls()
    if active_calls[0]:
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