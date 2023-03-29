import sys
import audio_recorder
import audio_transcriber
import text_to_speech
import audio_player

def main():
    # Initialize objects
    audio_recorder     = AudioRecorder()
    transcriber        = AudioTranscriber()
    tts                = TextToSpeech()
    player             = AudioPlayer()

    while True:
        # Record audio from the user's microphone
        print("Recording... Press Ctrl+C to stop.")
        try:
            audio_recording = audio_recorder.record_audio()
        except KeyboardInterrupt:
            print("Recording stopped.")
            break

        # Transcribe the recorded audio into text
        print("Transcribing audio...")
        transcribed_text = transcriber.convert_to_text(audio_recordering)

        # Convert the transcribed text back into an audio file
        print("Generating speech from text...")
        speech_audio   = tts.text_to_speech(transcribed_text)

        # Play the generated audio file
        print("Playing generated audio...")
        player.play_audio(speech_audio)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Program terminated.")
        sys.exit()
