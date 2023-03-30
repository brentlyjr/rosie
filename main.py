
from passage import Passage
import time

newPassage = Passage(text = "The rain in spain stays mainly in the plain")
print("The passage text:")
print(newPassage.get_text())

print("Translate to speech")
newPassage.translate_to_speech()

print("Let's play it")
newPassage.play_audio()

time.sleep(3)  # This is where I get stuck in resource problems occasionally (I think conflicts over sound)
print("Now let's record our message - about 8 seconds")
newPassage.record_audio(duration = 8)

print("recording finished")
newPassage.play_audio()

print("Translate to text")
newPassage.translate_to_text()
print(newPassage.get_text())

print("Done for now")