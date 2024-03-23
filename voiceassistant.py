import json
import time
import os
from openai import OpenAI
from datetime import datetime

class VoiceAssistant:

    PHRASE_CONTINUING = 0
    LAST_PHRASE_IN_RESPONSE = 1
    LAST_PHRASE_IN_CONVERSATION = 2

    def __init__(self):
        self.client = OpenAI()
#        self.model="gpt-3.5-turbo"       # currently hardcoded
        self.model="gpt-4"       # currently hardcoded
        self.system_prompt = ""
        self.messages = []
        self.reservation_name = "Joe Biden"
        self.party_size = 7
        self.reservation_date = "tomorrow"
        self.reservation_time = "7:30 PM"
        self.special_requests = "vegetarian, inside seating"
        self.stream = None

    def load_system_prompt(self):
        directory="templates"

        template_file = os.path.join(directory, "rosie_prompt.txt")

        with open(template_file, 'r') as file:
            prompt_template = file.read()

        final_string = prompt_template.format(
            PARTY_SIZE=self.party_size,
            RESERVATION_NAME=self.reservation_name,
            RESERVATION_DATE=self.reservation_date,
            RESERVATION_TIME=self.reservation_time,
            SPECIAL_REQUESTS=self.special_requests)

        # Seed our ChatGPT session with our initial prompt
        self.add_message(final_string, "system")

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
        #print_time_tracking2(start_time, "start_next_assist")
        parsed_messages = [{"role": item["role"], "content": item["message"]} for item in self.messages]

        self.stream = self.client.chat.completions.create(
            model=self.model,
            messages=parsed_messages,
            stream=True,
        )

    def next_chunk(self):
        partial_msg = ""
        assistant_msg = ""

        while True:
            chunk = next(self.stream)
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

    '''
    def call_and_response(self, msg=''):
        self.next_user_response(msg)
        self.next_assistant_response()
        for chunk in self.next_chunk():
            pass
        self.print_thread()
    '''

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

    def set_party_size(self, party_size):
        self.party_size = party_size

    def set_reservation_date(self, reservation_date):
        self.reservation_date = reservation_date

    def set_reservation_time(self, reservation_time):
        self.reservation_time = reservation_time

    def set_special_requests(self, special_requests):
        self.special_requests = special_requests

    def set_reservation_name(self, reservation_name):
        self.reservation_name = reservation_name


def print_time_tracking2(start_time, function_name):
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"TIMING: {function_name}  Execution time: {elapsed_time} seconds")