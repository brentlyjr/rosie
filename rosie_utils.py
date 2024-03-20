import os
import time
import requests


def load_environment_variable(str):
    # Loads an environment variable into a physical variable and returns it
    envVar = os.environ.get(str)
    if envVar is None:
        raise EnvironmentError(f"Error: Environment variable {str} is not set.")
    return envVar


def get_ngrok_ws_url():
    # Query ngrok API to get the tunnel information
    http_url = get_ngrok_http_url()

    # Switch the http protocol for a websocket and append our local path
    ws_url = http_url.replace("https", "wss")
    ws_url = ws_url + "/ws"
    print("Websocket URL =", ws_url)
    return ws_url


def get_ngrok_http_url():
    # Query ngrok API to get the tunnel information
    try:
        ngrok_tunnels = requests.get("http://127.0.0.1:4040/api/tunnels").json()

        # Loop through all the tunnels active on this machine
        for tunnel in ngrok_tunnels.get("tunnels", []):
            # If we have a tunnel that is coming to our local computer, this is the tunnel we want
            if tunnel.get("config", {}).get("addr") == "http://localhost:8080":

                # Extract the public URL of that tunnel
                http_url = tunnel.get("public_url")

        # Switch the http protocol for a websocket and append our local path
        return http_url

    except requests.ConnectionError:
        print("Could not connect to ngrok API")
        return None


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

    def reset(self):
        self.start_times = {}

# Our global profiler to give us overall timing of various components
profiler = Profiler()
    

