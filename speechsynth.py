from abc import ABC, abstractmethod
from dotenv import load_dotenv
import os
import requests
import json
import time

class SpeechSynth(ABC):
    def __init__(self, language):
        self.language = language

    @abstractmethod
    def translate_to_speech(self, text):
        pass


# API website to get your (free) key: https://rapidapi.com/k_1/api/large-text-to-speech/

class RapidAPISynth(SpeechSynth):

    def __init__(self, language):
        super().__init__(language)
        load_dotenv()  # Load environment variables from .env file
        self.api_key = os.environ.get('RAPIDAPI_KEY')
        self.filename = 'output.wav'

    def translate_to_speech(self, text):
        url = "https://large-text-to-speech.p.rapidapi.com/tts"

        headers = {
            'content-type': "application/json",
            'x-rapidapi-host': "large-text-to-speech.p.rapidapi.com",
            'x-rapidapi-key': self.api_key
            }

        url = "https://large-text-to-speech.p.rapidapi.com/tts"
        payload = {"text": text}



        # POST request
        response = requests.request("POST", url, data=json.dumps(payload), headers=headers)
        #print(response.text)

        # get id and eta of the job from the response
        id = json.loads(response.text)['id']
        eta = json.loads(response.text)['eta']

        print(f'Waiting {eta} seconds for the job to finish...')
        time.sleep(eta)

        # GET the result from the API
        response = requests.request("GET", url, headers=headers, params={'id': id})
        # if url not returned yet, wait and try again
        while "url" not in json.loads(response.text):
            response = requests.get(url, headers=headers, params={'id': id})
            time.sleep(5)
        # if no error, get url and download the audio file
        if not "error" in json.loads(response.text):
            result_url = json.loads(response.text)['url']
            # download the waw file from results_url
            response = requests.get(result_url)
            # save the waw file to disk
            with open(self.filename, 'wb') as f:
                f.write(response.content)
            print("File saved!", self.filename)
            return self.filename
        else:
            return(json.loads(response.text)['error'])

        
