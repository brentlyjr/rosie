import os
import io
import time
import audioop
import wave
import numpy as np


# Function to generate silence of given duration for Mu-Law
def generate_silence_pcm(duration, sample_rate):
    num_samples = int(duration * sample_rate)
    return bytes(np.zeros(num_samples, dtype=np.int16))


# This class is how we manage multiple chunks of text being synthesized at the same time
class AudioBuffer:

    def __init__(self, call_sid):
        self.last_save_time = time.time()
        self.saved_inbound_call_buffer = io.BytesIO() # Does not need to be threadsafe as we only have one writer and one reader from this stream
        self.saved_outbound_call_buffer = io.BytesIO()
        self.call_sid = call_sid
        self.audio_dir = "saved_audio"

    def save_inbound_audio_stream(self, raw_ulaw_data):
        # Convert from mulaw to PCM which is what the WAVE format expects
        pcm_data = audioop.ulaw2lin(raw_ulaw_data, 2)

        # Write the new chunk to the end of our internal buffer that we are keeping
        self.saved_inbound_call_buffer.write(pcm_data)

        # Save our file to file system every 2 seconds to support our live streaming
        current_time = time.time()
        if current_time - self.last_save_time >= 2:
            self.save_audio_recording()
            self.last_save_time = current_time

    def save_outbound_audio_stream(self, raw_ulaw_data, time_to_insert):
        # Convert from mulaw to PCM which is what the WAVE format expects
        pcm_data = audioop.ulaw2lin(raw_ulaw_data, 2)

        sample_rate = 8000 # Our mulaw is 8k right now

        # Get the current write pointer position
        current_position = self.saved_outbound_call_buffer.tell()

        # Calculate the duration of existing data in the buffer
        duration_before_insertion = current_position / (2 * sample_rate)  # 2 bytes per sample for 16-bit PCM

        # Calculate the duration of silence needed before the insertion point
        silence_duration = time_to_insert - duration_before_insertion

        # If silence is needed, insert silence
        if silence_duration > 0:
            silence_data = generate_silence_pcm(silence_duration, sample_rate)
            self.saved_outbound_call_buffer.write(silence_data)

        self.saved_outbound_call_buffer.write(pcm_data)

    def save_audio_recording(self):
        # Save the contents of the BytesIO buffer to a binary file
        # It is in the format U-Law - Default Endianess, 1-channel and a 8K sample rate

        # Test code to see the 2 raw channels
        # with open('output1.bin', 'wb') as f:
        #    f.write(self.saved_inbound_call_buffer.getvalue())
        # with open('output2.bin', 'wb') as f:
        #    f.write(self.saved_outbound_call_buffer.getvalue())

        # Read PCM data from buffers
        pcm_data1 = np.frombuffer(self.saved_inbound_call_buffer.getvalue(), dtype=np.int16)
        pcm_data2 = np.frombuffer(self.saved_outbound_call_buffer.getvalue(), dtype=np.int16)

        # Ensure both PCM data arrays have the same length
        max_length = max(len(pcm_data1), len(pcm_data2))
        pcm_data1 = np.pad(pcm_data1, (0, max_length - len(pcm_data1)))
        pcm_data2 = np.pad(pcm_data2, (0, max_length - len(pcm_data2)))

        # Merge PCM data into mono format by adding samples together
        merged_data = pcm_data1 + pcm_data2

        # Combine PCM data into stereo format
        # stereo_data = np.array([pcm_data1, pcm_data2], dtype=np.int16).T

        base_filename = f"{self.call_sid}.wav"
        sound_file = os.path.join(self.audio_dir, base_filename)

        # Open a new WAV file for writing
        with wave.open(sound_file, 'wb') as wf:
            wf.setnchannels(1)  # Mono
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(8000)  # Sample rate
            wf.writeframes(merged_data.tobytes())
