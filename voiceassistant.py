import json
import time
from openai import OpenAI
from datetime import datetime

class VoiceAssistant:
    def __init__(self, model):
        self.client = OpenAI()
        self.model="gpt-4"       # currently hardcoded
        self.system_prompt = self.get_system_prompt()
        self.messages = []
        self.add_message(self.system_prompt, "system")
    
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
If there are no vegetarian options available, please decline the reservation, thank the restaurant, and end the call

Please keep your responses short, only 1 or 2 sentences at a time. And please ask no more than one question at a time.

Please make the reservation under the name Joe Biden and the phone number if it's asked for is 415-123-4567"""
    
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
        parsed_messages = [{"role": item["role"], "content": item["message"]} for item in self.messages]
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=parsed_messages,
            stream=True,
        )
        assistant_msg = ""
        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                assistant_msg += chunk.choices[0].delta.content

        self.add_message(assistant_msg, "assistant")
        return(assistant_msg)
        
    def show_messages(self):
        messages=self.client.beta.threads.messages.list(thread_id=self.thread.id)
        show_json(messages)

    def last_message(self):
        return self.messages[-1]
    
    def print_thread(self):
        for message in self.messages[1:]:   # omit the system prompt since so long
            print(f"{message['created']}: {message['role']}: {message['message']}")

    def call_and_response(self, msg=''):
        self.next_user_response(msg)
        self.next_assistant_response()
        self.print_thread()
        
def show_json(obj):
    display(json.loads(obj.model_dump_json()))