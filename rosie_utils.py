import os
from dotenv import load_dotenv
import time

def load_environment_variables():
    if not os.path.exists('.env'):
        print("Warning: The .env file is missing.")

    load_dotenv()
    
    required_variables = ["SPEECH_KEY", "SPEECH_REGION", "SERVICE_PORT", "WEBSOCKET_STREAM_URL"]
    for variable in required_variables:
        if os.environ.get(variable) is None:
            raise EnvironmentError(f"Error: Environment variable {variable} is not set.")

    SPEECH_KEY = os.environ.get("SPEECH_KEY")
    SPEECH_REGION = os.environ.get("SPEECH_REGION")
    SERVICE_PORT = int(os.environ.get("SERVICE_PORT"))
    WEBSOCKET_STREAM_URL = os.environ.get("WEBSOCKET_STREAM_URL")

    return SPEECH_KEY, SPEECH_REGION, SERVICE_PORT, WEBSOCKET_STREAM_URL


class Profiler:
    def __init__(self):
        # Initialize a dictionary to store the start times for each keyword
        self.start_times = {}

    def update(self, keyword):
        # Record the current time for the given keyword
        self.start_times[keyword] = time.time()

    def __str__(self):
        # Calculate and return the string representation of elapsed time for each keyword in sorted order
        current_time = time.time()
        results = []
        for keyword in sorted(self.start_times):
            elapsed_time = current_time - self.start_times[keyword]
            results.append(f"{keyword}: {elapsed_time:.1f}")
        return "  ".join(results)
    
    def print(self, keyword):
        all_results = str(self)
        prefix = f"PROFILE({keyword}):".ljust(35)
        #print(f"{prefix}{all_results}")
