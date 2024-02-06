import os
from dotenv import load_dotenv
import time

def load_environment_variable(str):
    # Loads an environment variable into a physical variable and returns it
    envVar = os.environ.get(str)
    if envVar is None:
        raise EnvironmentError(f"Error: Environment variable {str} is not set.")
    return envVar


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
