import json
from typing import List
from datetime import datetime
from twilio.rest import Client
from rosie_utils import load_environment_variable, get_ngrok_http_url


# This class represents one call Rosie is managing. This is either an outbound call that was started from a
# server API, or an inbound call directly to our phone number. All of the assistant and voice recognition
# values are local to this call so we can have multiple calls going on simultaneously.
class OutboundCall:

    # Constructor that takes the to and from numbers directly
    def __init__(self, to_number, from_number, call_sid):
        self.to_number = to_number
        self.from_number = from_number
        self.call_sid = call_sid
        self.status = None
        self.stream_id = 0
        self.voice_assistant = None
        self.time_to_respond = False
        self.start_recognition = False
        self.start_time = datetime.now()
        self.duration = 0           # System timestamp in milliseconds
        self.TWILIO_ACCOUNT_SID = load_environment_variable("TWILIO_ACCOUNT_SID")
        self.TWILIO_AUTH_TOKEN = load_environment_variable("TWILIO_AUTH_TOKEN")

    # Constructor that takes a JSON object with the to and from numbers
    @classmethod
    def from_string(cls, json_str):
        try:
            # Parse our json string
            data = json.loads(json_str)
            # Extract variables from JSON data
            to_num = data.get("TO_NUMBER", 0)
            from_num = data.get("FROM_NUMBER", 0)
        except json.JSONDecodeError:
            print("Error: Failed to decode JSON")

        return cls(to_num, from_num, 0)

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

    def get_json_str(self):
        data = self.get_history_obj()
        return json.dumps(data, indent=4)

    def get_history_obj(self):
        data = {
            "sid": self.call_sid,
            "to_number": self.to_number,
            "from_number": self.from_number,
            "start_time": str(datetime.fromtimestamp(self.start_time)),
            "duration": self.duration
        }
        return data 

    def hang_up(self):
        call = Client(self.TWILIO_ACCOUNT_SID, self.TWILIO_AUTH_TOKEN).calls(self.call_sid).fetch()
        result = call.update(status='completed')
        print("Hangup initiated: ", result)

    def get_to_number(self):
        return self.to_number

    def get_from_number(self):
        return self.from_number

    def get_call_sid(self):
        return self.call_sid
    
    def get_status(self):
        return self.status
    
    def set_status(self, status):
        self.status = status

    def get_synthesizer(self):
        return self.synthesizer
    
    def get_recognizer(self):
        return self.recognizer
    
    def set_synthesizer(self, synth):
        self.synthesizer = synth

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

    def set_start_time(self, starttime):
        self.start_time = starttime

    def get_start_time(self):
        return self.start_time
    
    def get_duration(self):
        return self.duration
    
    def set_duration(self, duration: int):
        self.duration = duration


# The call manager class maintains a list of all the currently existing calls being made "to" or "from" rosie
# This is a singleton class, so we can never instantiate more than one of these classes.
class CallManager:
    
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.objects = {}
            cls._instance.unique_ids = set()
            cls._instance.history_file = "history.json"
        return cls._instance

    def add_call(self, call_sid, call_obj):
        if call_sid in self.unique_ids:
            raise ValueError(f"Call with ID {call_sid} already exists.")
        self.objects[call_sid] = call_obj
        self.unique_ids.add(call_sid)

    def remove_call(self, call_sid):
        if call_sid not in self.unique_ids:
            raise ValueError(f"Call with ID {call_sid} does not exist.")
        del self.objects[call_sid]
        self.unique_ids.remove(call_sid)

    def get_call(self, call_sid):
        return self.objects.get(call_sid, None)

    def get_all_calls(self):
        return list(self.objects.values())
    
    def save_history(self, call):
        history_obj = call.get_history_obj()
        with open(self.history_file, 'a') as file:

            # Write the new history_obj to the file
            json.dump(history_obj, file)

            # Add a newline character to separate the new object from the existing content
            file.write('\n')

    def get_history(self) -> List[dict]:
        try:
            with open(self.history_file, 'r') as file:
                data = [json.loads(line) for line in file]
        except FileNotFoundError:
            # If the history file does not exist, return an empty list
            print("No history file exists yet")
            data = []
        return data
