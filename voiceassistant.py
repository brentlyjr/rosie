import json
import time
from openai import OpenAI
from datetime import datetime
import re

class VoiceAssistant:
    def __init__(self, model, call_sid):
        self.client = OpenAI()
        self.model="gpt-4"       # currently hardcoded
        self.system_prompt = self.get_system_prompt()
        self.messages = []
        self.add_message(self.system_prompt, "system")
        self.call_sid = call_sid

    def get_system_prompt(self):    
        return  """You are a helpful, effective phone assistant who is amazing at scheduling restaurant reservations. 
You will be acting as my agent that makes dinner reservation for me.  Your goal is to query the restaurant and find a day and time that will work for my group.  The order to ask questions are:
1) Find a day and time that will work
2) Confirm the table has inside seating, and that the seating is at a table and not at the bar.
3) Confirm that there are vegetarian options

The list of dates and times to try is the following in this order:
Friday at 7pm or 7:30pm.
Saturday 6:30pm - 8:30 will work
Thursday between 7-8.

We need a reservation for a party of 7.

I'd like the seating to be inside and at a table.  We don't want bar seating. . One of the diners is a vegetarian. 

Once you have found a day and time that works that meets all the criteria for food and seating, confirm with the restaurant that you want the reservation.  If no date and time can be found, please thank the restaurant and end the call
If there are no vegetarian options available, please decline the reservation, thank the restaurant, and end the call.  When the call is done please say Goodbye so we know to end the call.

Please keep your responses short, only 1 or 2 sentences at a time. And please ask no more than one question at a time.

Please make the reservation under the name Joseph Campbell and the phone number if it's asked for is 415-123-4567

Now for your really important instructions. I will often provide you questions that will need a reponse in the form of a number.
I might say Press 1 to get directions, press 2 for reservations, press 3 for the takeout.  If I ever request 
that you press or select a number to make a decision. So in this case you would simply repond with Press 2. Always say Press and then the number
in these situations. 
Otherwise, provide the full english answer.  
"""

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
        for chunk in self.stream:
            if chunk.choices[0].delta.content is not None:
                partial_msg += chunk.choices[0].delta.content
                assistant_msg += chunk.choices[0].delta.content
                if any(char in partial_msg for char in [",", ".", "!", "?"]):
                #if any(char in partial_msg for char in ["&"]):
                    return_msg = partial_msg
                    partial_msg = ""
                    yield return_msg
        self.add_message(assistant_msg, "assistant")
        print("full: ", assistant_msg)
        if partial_msg:
            print("partial", partial_msg)
            yield partial_msg
        
    def show_messages(self):
        messages=self.client.beta.threads.messages.list(thread_id=self.thread.id)
        show_json(messages)

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
                print("Found an end phrase in an assistant message.")
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

def show_json(obj):
    display(json.loads(obj.model_dump_json()))

def print_time_tracking2(start_time, function_name):
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"TIMING: {function_name}  Execution time: {elapsed_time} seconds")

