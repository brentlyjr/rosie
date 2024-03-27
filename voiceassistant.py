import time
from openai import OpenAI
from datetime import datetime
import re
from typing import Dict, Tuple, Set
from filemanager import FileManager
from types import SimpleNamespace

class VoiceAssistant:

    PHRASE_CONTINUING = 0
    LAST_PHRASE_IN_RESPONSE = 1
    LAST_PHRASE_IN_CONVERSATION = 2

    """
     instruct_params - dictionary containing custom info for caller or caller. Currently from client web app
         E.g. first_name, phone number, specific instructions.  All customized info.

     Key parameter: CALLTYPE - indicates kind of call and script (doctor appt, dinner reservation, etc) 
        CALLTYPE list in config.ini file
    """
    def __init__(self, model, instruct_params: dict) -> None:
        self.client = OpenAI()
        self.model=model                  # currently hardcoded
        self.messages = []
        self.intro_message = True           # forces an introduction message to be played first.  Set to false for no intro message.
        self.filemanager = FileManager()

        self._load_system_prompt(instruct_params)
        self.stream = None

    def _load_system_prompt(self, instruct_params: dict) -> None:
        """
        Creates system prompt from files and interpolated data   

            CALLTYPE key (in instruct_params) determines prompt

            Interpolated data - dictionaries to interpolate into prompt
                instruct_params - contains specific, customized call info  
                llm_general_system_prompt - file with general info (in config.ini) 
        """
        generic_params = self.filemanager.read_data('llm_general_system_prompt')
        #strip new line if it ends with one
        for key in generic_params:
            generic_params[key] = generic_params[key].rstrip("\n")
        
        # Combine generic_params and instruct_param, with values from instruct_params overriding those from generic_params in case of conflicts
        self.all_params = {**generic_params, **instruct_params}

        final_string, unused_params, remaining_placeholders = self._replace_from_file(instruct_params['CALLTYPE'])
        if unused_params: print(f"ERROR: Unused parameters: {unused_params}")                 
        if remaining_placeholders: print(f"ERROR: Placeholders not filled in: {remaining_placeholders}") 

        # Seed our ChatGPT session with our initial prompt
        self.add_message(final_string, "system")
        print(f"system messsage {final_string}" )

    def add_message(self, msg, role):
        current_datetime = datetime.now()
        # Convert to a timestamp (seconds since the Unix epoch)
        timestamp = int(current_datetime.timestamp())
        self.messages.append({"created":timestamp, "role":role, "message":msg})

    def next_user_response(self, msg):
        # Check if the message_list is not empty
        if msg:
            self.add_message(msg, "user")           
            return msg
        else:
            # Return None if the list is empty
            return None

    def next_assistant_response(self):
        start_time = time.time()
        # Added this to force an introduction message
        if not self.intro_message:
            parsed_messages = [{"role": item["role"], "content": item["message"]} for item in self.messages]

            self.stream = self.client.chat.completions.create(
                model=self.model,
                messages=parsed_messages,
                stream=True,
            )
        else:
            self.stream = self._get_intro_message()
            self.intro_message = False

    def _get_intro_message(self):
        """
        Allows us to create a standard introduction message for every call.  Ensures some comformity.
           intro message (found in introduction file - config.ini) can be customized via interpolation
           parameters passed in on intial call invocation will be used to modify intro message

        """
        intro_message, _, remaining_placeholders = self._replace_from_file('introduction')
        if remaining_placeholders: print(f"ERROR: Placeholders not filled for intro in: {remaining_placeholders}") 
        
        #Build up the data structure to match OpenAI streaming object. In this case provide all the text immediately.
        stream = [
            {"choices": [{"delta": {"content": intro_message}}]} ]
        
        # This converts the nested dictionaries into simple objects so it can be read out correctly in next_chunk
        stream = [dict_to_simplenamespace(chunk) for chunk in stream]
        return iter(stream)

    def next_chunk(self):
        partial_msg = ""
        assistant_msg = ""

        while True:
            try:
                chunk = next(self.stream)
            except StopIteration:
                break

            msg = chunk.choices[0].delta.content
            if msg is not None:
                partial_msg += msg
                assistant_msg += msg
                # Check for any of the tokens that we might use to indicate a good time to pause
                # in the speech synthesis
                if any(char in partial_msg for char in [",", ".", "!", "?"]):
                    return_msg = partial_msg
                    partial_msg = ""
                    yield return_msg, VoiceAssistant.PHRASE_CONTINUING
            else:
                # We have finished our phrase and now can append it to our master conversation list
                self.add_message(assistant_msg, "assistant")

                # Since we have no more data to process, do a check to see if we received anything that would
                # indicate we are at the end of the conversation
                if self.conversation_ended():
                    print("assistant_message: ", assistant_msg)
                    yield '', VoiceAssistant.LAST_PHRASE_IN_CONVERSATION
                # Otherwise, we are just at the end of our speaking time
                else:
                    yield '', VoiceAssistant.LAST_PHRASE_IN_RESPONSE
                break  # Exit the loop if content is None

    def last_message(self):
        return self.messages[-1]

    def last_message_text(self):
        return self.messages[-1]['message']

    def print_thread(self):
        for message in self.messages[1:]:   # omit the system prompt since so long
            print(f"{message['created']}: {message['role']}: {message['message']}")

    def call_and_response(self, msg=''):
        self.next_user_response(msg)
        self.next_assistant_response()
        for chunk in self.next_chunk():
            pass
        self.print_thread()

    def find_press_digits(self, text):
        # Regular expression pattern to find "Press {digits}"
        pattern = r"Press (\d+)"
        
        # Find all matches
        matches = re.findall(pattern, text)
        
        # Check if there are any matches and return the first one
        if matches:
            return matches[0]
        else:
            return None
    
    def conversation_ended(self):
        # Array of phrases to check for
        end_phrases = ["goodbye", "see you later", "farewell", "bye", "great day"]
    
        for message in reversed(self.messages):
            # Convert the message to lowercase to make the search case-insensitive
            message_content_lower = message['message'].lower()
    
            # Check if the role is 'assistant' and if any of the end phrases are in the message
            if message['role'] == 'assistant' and any(phrase in message_content_lower for phrase in end_phrases):
                print("Found an end phrase in an assistant message: ", message_content_lower)
                return True
    
        return False

    def summarize_conversation(self):
        instruct = """Please write a concise summary of the reservation that includes the name of the restaurant,
        the time and date and any special instructions that were agreed to by the restaurant.  Please include any interesting details from the conversation.""" 
        self.next_user_response(instruct)
        self.next_assistant_response()
        for chunk in self.next_chunk():
            pass
        msg = self.last_message()
        print("RESERVATION Summary: ", msg['message'])

    def _replace_from_file(self, file_token: str):
        return replace_placeholders(self.filemanager.read_data(file_token), self.all_params)


def replace_placeholders(text: str, data: Dict[str, str]) -> Tuple[str, Dict[str, str], Set[str]]:
    """
    Replaces placeholders in the text with values from the data dictionary and
    identifies unused keys/values and unreplaced placeholders.

    Parameters:
    - text (str): The text containing placeholders to be replaced.
    - data (Dict[str, str]): A dictionary where keys are placeholders (without curly braces)
                             and values are the replacements for those placeholders.

    Returns:
    - Tuple[str, Dict[str, str], Set[str]]: The text with placeholders replaced by corresponding data dictionary values,
                                              unused key/value pairs from the data dictionary,
                                              and unreplaced placeholders in the text.
    """
    used_keys = set()
    # Replace placeholders with values from the data dictionary
    for key, value in data.items():
        placeholder = "{" + key + "}"
        if placeholder in text:
            text = text.replace(placeholder, str(value))
            used_keys.add(key)

    # Identify unused keys/values in the data dictionary
    unused_data = {key: value for key, value in data.items() if key not in used_keys}

    # Attempt to find any unreplaced placeholders in the text
    unreplaced_placeholders = set()
    start = 0
    while True:
        start_idx = text.find('{', start)
        if start_idx == -1:
            break
        end_idx = text.find('}', start_idx)
        if end_idx == -1:
            break
        placeholder = text[start_idx:end_idx + 1]
        unreplaced_placeholders.add(placeholder)
        start = end_idx + 1

    # Filter out placeholders that were actually replaced
    unreplaced_placeholders = {ph for ph in unreplaced_placeholders if ph[1:-1] not in used_keys}

    return text, unused_data, unreplaced_placeholders
    
def print_time_tracking2(start_time, function_name):
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"TIMING: {function_name}  Execution time: {elapsed_time} seconds")


def dict_to_simplenamespace(d):
    """
    Converts nested dictionaries into simple objects.  
    Needed so internal structures can be accessed  obj1.obj2  instead of obj1['obj2']
    """
    for key, value in d.items():
        if isinstance(value, dict):
            d[key] = dict_to_simplenamespace(value)
        elif isinstance(value, list):
            d[key] = [dict_to_simplenamespace(item) if isinstance(item, dict) else item for item in value]
    return SimpleNamespace(**d)

