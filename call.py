import io
import os
import wave
import audioop
import json
import time
from twilio.rest import Client
from datetime import datetime
from rosie_utils import load_environment_variable, get_ngrok_http_url


# This class represents one call Rosie is managing. This is either an outbound call that was started from a
# server API, or an inbound call directly to our phone number. All of the assistant and voice recognition
# values are local to this call so we can have multiple calls going on simultaneously.
class Call:

    # Constructor that takes the to and from numbers directly
    def __init__(self, to_number, from_number, call_sid=0):
        self.to_number = to_number
        self.from_number = from_number
        self.call_sid = call_sid
        self.status = None
        self.stream_id = 0
        self.voice_assistant = None
        self.synthesizer = None
        self.time_to_respond = False
        self.start_recognition = False
        self.call_ending = False    # Once this is invoked, we know to start cleaning up all call resources
        self.set_start_time()
        self.duration = 0           # System timestamp in milliseconds
        self.TWILIO_ACCOUNT_SID = load_environment_variable("TWILIO_ACCOUNT_SID")
        self.TWILIO_AUTH_TOKEN = load_environment_variable("TWILIO_AUTH_TOKEN")
        self.audio_dir = "saved_audio"
        self.audio_stream = None

    # Parse the json passed into this class
    def load_json(self, json_str):
        try:
            # Parse our json string
            data = json.loads(json_str)
            # Extract variables from JSON data
            self.to_number = data.get("TO_NUMBER")
            self.from_number = data.get("FROM_NUMBER")
        except json.JSONDecodeError:
            print("Error: Failed to decode JSON")

    def make_call(self):
        print("Starting our outbound call")
        client = Client(self.TWILIO_ACCOUNT_SID, self.TWILIO_AUTH_TOKEN)

        twilioUrl = get_ngrok_http_url()
        # call = client.calls.create(
        #                     method='POST',
        #                     url=twilioUrl+'/api/callback',
        #                     machine_detection='Enable',
        #                     async_amd_status_callback=twilioUrl+'/api/machinedetect',
        #                     async_amd='true',
        #                     to=self.to_number,
        #                     from_=self.from_number,
        #                     status_callback=twilioUrl+'/api/callstatus',
        #                     status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
        #                     status_callback_method='POST'
        #                 )

        call = client.calls.create(
                            method='POST',
                            url=twilioUrl+'/api/callback',
                            to=self.to_number,
                            from_=self.from_number,
                            status_callback=twilioUrl+'/api/callstatus',
                            status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
                            status_callback_method='POST'
                        )
      
        self.call_sid = call.sid
        print("Call SID: ",self.call_sid)
        return self.call_sid

    def answer_type(self):
        call = Client(self.TWILIO_ACCOUNT_SID, self.TWILIO_AUTH_TOKEN).calls(self.call_sid).fetch()
        return call.answered_by
    
    def get_json_str(self):
        data = self.get_history_obj()
        return json.dumps(data, indent=4)

    def get_history_obj(self):
        data = {
            "sid": self.call_sid,
            "to_number": self.to_number,
            "from_number": self.from_number,
            "start_time": str(datetime.fromtimestamp(self.start_time)),
#            "start_time": str((self.start_time)),
            "duration": self.duration
        }
        return data 

    # What is the difference between executing OutboundCall.hang_up and 
    def hang_up(self):
        call = Client(self.TWILIO_ACCOUNT_SID, self.TWILIO_AUTH_TOKEN).calls(self.call_sid).fetch()
        result = call.update(status='completed')
        print("Hangup initiated: ", self.call_sid)
        # Once we have hang up, we need to make our call has done so all resources get cleaned up properly
        self.set_call_ending(True)

    def get_to_number(self):
        return self.to_number
    
    def get_call_ending(self):
        return self.call_ending

    def get_from_number(self):
        return self.from_number

    def get_call_sid(self):
        return self.call_sid
    
    def get_status(self):
        return self.status
    
    def set_status(self, status):
        self.status = status

    def get_synthesizer_manager(self):
        return self.synthesizer

    def set_synthesizer_manager(self, synth):
        self.synthesizer = synth

    def get_recognizer(self):
        return self.recognizer
    
    def set_recognizer(self, recog):
        self.recognizer = recog

    def get_stream_id(self):
        return self.stream_id
    
    def set_stream_id(self, stream_id):
        self.stream_id = stream_id

    def get_voice_assistant(self):
        return self.voice_assistant
    
    def set_voice_assistant(self, assistant):
        self.voice_assistant = assistant

    def get_respond_time(self):
        return self.time_to_respond
    
    def set_respond_time(self, time_to_respond: bool):
        self.time_to_respond = time_to_respond

    def get_start_recognition(self):
        return self.start_recognition
    
    def set_start_recognition(self, start_recognition: bool):
        self.start_recognition = start_recognition

    def set_start_time(self):
        self.start_time = time.time()

    def get_start_time(self):
        return self.start_time
    
    def get_duration(self):
        return self.duration
    
    def set_duration(self, duration: int):
        self.duration = duration

    def set_call_ending(self, call_ending: bool):
        self.call_ending = call_ending