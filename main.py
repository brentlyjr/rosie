
from passage import Passage
import time

newPassage = Passage(text = "The rain in spain stays mainly in the plain")
print("\nThe passage text:", newPassage.get_text())

print("Translate to speech")
newPassage.translate_to_speech()

print("Let's play it")
newPassage.play_audio()

time.sleep(6) 

print("Now let's record our message - about 8 seconds")
duration =8
newPassage.record_audio(duration = duration)


newPassage.play_audio()
time.sleep(duration+1)

print("Translate to text")
newPassage.translate_to_text()
print(newPassage.get_text())

print("And change your voice")
newPassage.translate_to_speech()

print("Let's hear how you sound")
newPassage.play_audio()
time.sleep(duration+1)

print("Done for now")