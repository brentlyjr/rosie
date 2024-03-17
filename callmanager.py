import os
import io
import json
import wave
import audioop
from typing import List
from datetime import datetime
from twilio.rest import Client
from rosie_utils import load_environment_variable, get_ngrok_http_url


# This class represents one call Rosie is managing. This is either an outbound call that was started from a
# server API, or an inbound call directly to our phone number. All of the assistant and voice recognition
# values are local to this call so we can have multiple calls going on simultaneously.
class OutboundCall:

    # Constructor that takes the to and from numbers directly
    def __init__(self, to_number, from_number, call_sid=0):
        self.to_number = to_number
        self.from_number = from_number
        self.call_sid = call_sid
        self.status = None
        self.stream_id = 0
        self.voice_assistant = None
        self.time_to_respond = False
        self.start_recognition = False
        self.call_ending = False    # Once this is invoked, we know to start cleaning up all call resources
        self.start_time = datetime.now()
        self.duration = 0           # System timestamp in milliseconds
        self.TWILIO_ACCOUNT_SID = load_environment_variable("TWILIO_ACCOUNT_SID")
        self.TWILIO_AUTH_TOKEN = load_environment_variable("TWILIO_AUTH_TOKEN")
        self.call_stream = io.BytesIO() # Does not need to be threadsafe as we only have one writer and one reader from this stream
        self.audio_dir = "saved_audio"

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
        print("Hangup initiated: ", self.call_sid)
        # Once we have hang up, we need to make our call has done so all resources get cleaned up properly
        self.set_call_ending(True)

    def save_audio_recording(self):
        self.call_stream.seek(0)

        # Save the contents of the BytesIO buffer to a binary file
        # THis code is currently not being used. But this is the RAW data straight from the stream
        # It is in the format U-Law - Default Endianess, 1-channel and a 8K sample rate
        #
        # with open('output.bin', 'wb') as f:
        #    f.write(self.call_stream.getvalue())

        self.call_stream.seek(0)
        data = self.call_stream.getvalue()

        # Decode the μ-law encoded data to Linear PCM - this is what is needed to save out a WAVE file
        pcm_data = audioop.ulaw2lin(data, 2)

        base_filename = f"{self.call_sid}.wav"
        sound_file = os.path.join(self.audio_dir, base_filename)

        # Save the PCM data to a WAV file
        with wave.open(sound_file, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)   # 8-bit
            wav_file.setframerate(8000)  # Sample rate
            wav_file.writeframes(pcm_data)

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

    def set_call_ending(self, call_ending: bool):
        self.call_ending = call_ending


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
            cls._instance.audio_dir = "saved_audio"
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

    def get_saved_audio_stream(self, call_sid):
        # Returns a stream of the saved audio file for a particular call
        # Returns null if
        base_filename = f"{call_sid}.wav"
        sound_file = os.path.join(self.audio_dir, base_filename)
        print("Fetching sound file: ", sound_file)

        if not os.path.exists(sound_file):
            return None
        
        return open(sound_file, mode="rb")



# Instantiate our global call manager to track all concurrenet calls
rosieCallManager = CallManager()
