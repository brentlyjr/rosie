# Main dispatch controller for our Rosie Voice Assistance

import json
import uvicorn
import threading
import time
import base64
from fastapi import FastAPI, WebSocket, Request, WebSocketDisconnect
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from twilio.twiml.voice_response import VoiceResponse, Connect
from rosie_utils import load_environment_variable, Profiler, get_ngrok_ws_url, get_ngrok_http_url, profiler
from callmanager import OutboundCall, CallManager, rosieCallManager
from voiceassistant import VoiceAssistant
from speechsynth_azure import SpeechSynthAzure
from speechrecognizer_azure import SpeechRecognizerAzure
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates


# Load all the required environment variables with proper error checking
SPEECH_KEY = load_environment_variable("AZURE_SPEECH_KEY")
SPEECH_REGION = load_environment_variable("AZURE_SPEECH_REGION")
SERVICE_PORT = load_environment_variable("SERVICE_PORT")

# Some critical global variables
app = FastAPI()
templates = Jinja2Templates(directory="templates")


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
            # Only gets into this loop when we have another chunk of data back from ChatGPT
            profiler.print("Chat chunk")
            profiler.update("ChatGPT-chunk")
            print("Txt to convert to speech: ", synth_text)
            profiler.update("SpeechSynth")
            encoded_data = speech_synth.generate_speech(synth_text)
            profiler.print("Generate speech")

            # Send the encoded data over the WebSocket stream
            #print("Sending Media Message: ")
            await websocket.send_json(media_data(encoded_data, stream_id))
            call_obj.call_stream.write(base64.b64decode(encoded_data))
            profiler.print("Streaming AI Voice")

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

    if event == "connected":
        print("A new stream has connected for call:", call_sid)

    elif event == "start":
        stream_id = msg.get('streamSid')
        print(f"Starting Media Stream {stream_id}")

        # Because we are starting off our streams, let's instantiate the speech_synth and
        #  the speech_recognizer for this call
        speech_synth = SpeechSynthAzure(SPEECH_KEY, SPEECH_REGION, call_sid)
        speech_recognizer = SpeechRecognizerAzure(SPEECH_KEY, SPEECH_REGION, call_sid)

        # And store these with our call so we can retrieve them later
        call_obj = rosieCallManager.get_call(call_sid)
        call_obj.set_synthesizer(speech_synth)
        call_obj.set_recognizer(speech_recognizer)
        call_obj.set_stream_id(stream_id)

        # Start continuous speech recognition
        speech_recognizer.start_recognition()

    # The event that carries our audio stream
    elif event == "media":
        payload = msg['media']['payload']
        call_obj = rosieCallManager.get_call(call_sid)
        if call_obj.get_respond_time() == False:
            call_obj.call_stream.write(base64.b64decode(payload))
        if payload:
            speech_recognizer = call_obj.get_recognizer()
            speech_recognizer.write_stream(payload)
 
    elif event == "stop":
        print("Call Has Ended")
        call_obj = rosieCallManager.get_call(call_sid)
        call_obj.set_call_ending(True)


# This in our main clean-up API. This will get triggered when the call automatically is hung up
# through our twilio APIs or when the call has received a termination from the other side of the web socket
def cleanup_call(call_sid):
    print("Cleaning up call resources")
    call_obj = rosieCallManager.get_call(call_sid)
    speech_recognizer = call_obj.get_recognizer()
    speech_recognizer.stop_recognition()

    # Logic to close out the call by setting the duration and saving the history out
    timediff = time.time() - call_obj.get_start_time()
    call_obj.set_duration(timediff)
    print("Call had duration of " + str(call_obj.get_duration()) + " seconds.")

    # Save the history of our object to our database
    rosieCallManager.save_history(call_obj)
    call_obj.save_audio_recording()


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

        # Setup a Rosie voice assistant for this call with LLM and call id
        assistant = VoiceAssistant()

        # And load the system propmt so our call will execute with all the right details
        assistant.load_system_prompt()
        call_obj.set_voice_assistant(assistant)

        # Put this call in our active call queue for tracking
        rosieCallManager.add_call(call_sid, call_obj)

        # Mark this as an inbound call
        inbound_call = True

    # Make this as the starttime for our call
    call_obj.set_start_time(time.time())

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
    call_obj = rosieCallManager.get_call(call_sid)
    call_obj.set_status(status)

    '''
    # Taking this code out from here because inbound calls do not get call status events. Ideally this is
    # where the logic is to set start and end call events, but for now we will just keep them in other
    # places where we can manually detect these events.
    if status == 'initiated':
        call_obj.set_start_time(datetime.now())
    '''

    print("Call SID:", call_sid, "has status:", status)

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
    # Parse JSON request body for this call
    request_body = await request.json()

    # Extract our variables
    toNumber = request_body.get('TO_NUMBER', None)
    fromNumber = request_body.get('FROM_NUMBER', None)
    reservationName = request_body.get('RESERVATION_NAME', None)
    reservationDate = request_body.get('RESERVATION_DATE', None)
    reservationTime = request_body.get('RESERVATION_TIME', None)
    partySize = request_body.get('PARTY_SIZE', None)
    specialRequests = request_body.get('SPECIAL_REQUESTS', None)
    # promptMessage = request_body.get('PROMPT_MESSAGE', None)

    # Initiate a new call object for this call we are starting
    call_obj = OutboundCall(toNumber, fromNumber)

    # Setup a Rosie voice assistant for this call with LLM and call id
    assistant = VoiceAssistant()

    # Set all the tokens for our call
    assistant.set_party_size(partySize)
    assistant.set_reservation_date(reservationDate)
    assistant.set_reservation_time(reservationTime)
    assistant.set_special_requests(specialRequests)
    assistant.set_reservation_name(reservationName)

    # And load the system propmt so our call will execute with all the right details and save with call
    assistant.load_system_prompt()
    call_obj.set_voice_assistant(assistant)

    # Start the outbound call process
    call_sid = call_obj.make_call()

    # Add this to our queue of "live" outbound calls
    rosieCallManager.add_call(call_sid, call_obj)

    return {"message": "Making outbound call to: {toNumber} from: {fromNumber}"}


# Rest API call that returns all the call results stored in our local history
@app.get("/api/gethistory")
async def gethistory(request: Request):
    global rosieCallManager

    history_data = rosieCallManager.get_history()
    return history_data


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