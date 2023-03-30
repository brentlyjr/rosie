
from audiosnippet import PyAudioSnippet

my_audio = PyAudioSnippet()
duration = 5    # in seconds

print("starting to record")
my_audio.record_audio(duration)
print("recording finished")

print("Now translating to english")
text = my_audio.translate_to_text()
print(text)