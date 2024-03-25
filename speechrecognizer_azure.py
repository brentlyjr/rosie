import azure.cognitiveservices.speech as speechsdk
import base64
from callmanager import CallManager, rosieCallManager
from rosie_utils import Profiler, profiler


def recognizing_cb(evt, call_sid):
    global profiler
    global rosieCallManager

    call = rosieCallManager.get_call(call_sid)

    print("LISTENING: " + evt.result.text)
    if not call.get_start_recognition():
        profiler.update("Listening")
        call.set_start_recognition(True)


def recognized_cb(evt, call_sid):
    global profiler
    global rosieCallManager

    call = rosieCallManager.get_call(call_sid)
    assistant = call.get_voice_assistant()

    profiler.update("Recognized")
    call.set_start_recognition(False)
    txt = evt.result.text
    if not txt:
        print("RECOGNIZED: None ---- ENDING")
        return
    
    print("RECOGNIZED: " + txt)
    profiler.print("Recognized")

    # My edits - start translating as soon as there is a pause

    assistant.next_user_response(txt)
    print("-----------------------------------")
    profiler.update("ChatGPT-Full")
    profiler.update("ChatGPT-chunk")
    # Take our text response from the end-user and put it in our voice assistant for processing
    assistant.next_assistant_response()
    assistant.print_thread()
    profiler.print("Next_Assistant")
    print("-----------------------------------")

    # We now tell our call object it is time to respond back to the user
    call.set_respond_time(True)


class SpeechRecognizerAzure:
    def __init__(self, SPEECH_KEY, SPEECH_REGION, call_sid):
        self.speech_config = speechsdk.SpeechConfig(subscription=SPEECH_KEY, region=SPEECH_REGION)

        self.call_sid = call_sid
        # Let's allow swearing to come through
        self.speech_config.set_profanity(speechsdk.ProfanityOption.Raw)

        self.audio_format = speechsdk.audio.AudioStreamFormat(samples_per_second=8000,
                                                            bits_per_sample=8,
                                                            channels=1, 
                                                            wave_stream_format=speechsdk.AudioStreamWaveFormat.MULAW)
        self.push_stream = speechsdk.audio.PushAudioInputStream(stream_format=self.audio_format)
        self.audio_config = speechsdk.audio.AudioConfig(stream=self.push_stream)

        self.speech_recognizer = speechsdk.SpeechRecognizer(speech_config=self.speech_config, audio_config=self.audio_config)

        # Now instantiate our callbacks for these streams
        self.speech_recognizer.recognizing.connect(self.recognizing_callback)
        self.speech_recognizer.recognized.connect(self.recognized_callback)
        # These callbacks are not needed during normal operation
        # self.speech_recognizer.session_started.connect(lambda evt: print('SESSION STARTED: {}'.format(evt)))
        # self.speech_recognizer.session_stopped.connect(lambda evt: print('SESSION STOPPED {}'.format(evt)))
        # self.speech_recognizer.canceled.connect(lambda evt: print('CANCELED {}'.format(evt)))

    def recognizing_callback(self, evt):
        recognizing_cb(evt, self.call_sid)

    def recognized_callback(self, evt):
        recognized_cb(evt, self.call_sid)

    def write_stream(self, payload):
        # Decode our payload and append to our push stream
        self.push_stream.write(base64.b64decode(payload))

    def start_recognition(self):
        # Start continuous speech recognition
        self.speech_recognizer.start_continuous_recognition()

    def stop_recognition(self):
        # Stop the continuous recognition
        self.speech_recognizer.stop_continuous_recognition()
