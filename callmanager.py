import os
import json
from typing import List

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

    def add_call(self, call_sid, call):
        if call_sid in self.unique_ids:
            raise ValueError(f"Call with ID {call_sid} already exists.")
        self.objects[call_sid] = call
        self.unique_ids.add(call_sid)

    def remove_call(self, call_sid):
        if call_sid not in self.unique_ids:
            raise ValueError(f"Call with ID {call_sid} does not exist.")
        del self.objects[call_sid]
        self.unique_ids.remove(call_sid)

    def get_call(self, call_sid):
        return self.objects.get(call_sid, None)

    def get_all_calls(self):
        pass

    def get_active_calls(self) -> List[dict]:
        all_calls=[]
        for call in self.objects.values():
            history_obj = call.get_history_obj()
            all_calls.append(history_obj)
        return all_calls

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
    
    def get_live_audio_filename(self, call_sid):
        # Returns a stream of the saved audio file for a particular call
        # Returns null if
        destination_dir = "saved_audio"
        base_filename = f"{call_sid}.wav"
        sound_file = os.path.join(destination_dir, base_filename)
        return sound_file
    

# Instantiate our global call manager to track all concurrent calls
rosieCallManager = CallManager()