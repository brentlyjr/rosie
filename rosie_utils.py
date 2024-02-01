import os
from dotenv import load_dotenv

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
