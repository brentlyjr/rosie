import pyaudio
import struct
import os

# Audio configuration
FORMAT = pyaudio.paInt16

audio = pyaudio.PyAudio()

class LiveAudioStreamManager:

    _instance = None

    def __new__(cls, callmanager):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.live_audio_streams = []
            cls._instance.callmanager = callmanager
        return cls._instance

#    def __init__(self, callmanager):
#        self.callmanager = callmanager
#        self.live_audio_streams = []

    def play_stream(self, call_sid):
        # CHANNELS = 1
        # SAMPLE_RATE = 44100
        # CHUNK = 1024
        # CHANNELS = 2
        # BYTES_PER_SAMPLE = 2  # assuming 16-bit audio
        new_filesize = 2000*10**6 # this is to make a large buffer on the clients side for stream

        self.add_stream(call_sid)
        WAVE_FILE_PATH = self.callmanager.get_live_audio_filename(call_sid)
        with open(WAVE_FILE_PATH, 'rb') as f:
            header = f.read(44)
            parsed_header = parse_wave_header(header)

            # Read the initial 44 bytes for the WAV header
            # Go to the end of the file to find its size
            f.seek(0, os.SEEK_END)
            filesize = f.tell()
            
            # Calculate the starting position, adjusting so as not to re-send the header
            start_position = max(44, filesize - bytes_back(1, parsed_header))  # Ensure we start after the header
            f.seek(start_position)
            print("Sending audio file header")
            modified_header = modify_wave_file_size(header, new_filesize)
            # First, send the header
            yield modified_header
            
            # Initially read the data up to the current end and stream it
            data = f.read()
            yield data
            #no_data = 0
            # Continue streaming as the file grows
            while self.isActive(call_sid):
                data = f.read()
                if not data:
                    # For debugging
                    # no_data+=1
                    # if(not no_data%200000):
                    #     print("still no data:", no_data)
                    continue  # No new data, skip
                #print("STREAMING LIVE DATA SIZE: ", len(data))
                #no_data = 0
                yield data

    def stop_stream(self, call_sid):
        if(call_sid in self.live_audio_streams):
            self.live_audio_streams.remove(call_sid)

    def add_stream(self, call_sid):
        self.live_audio_streams.append(call_sid)
        
    def active_streams(self):
        return self.live_audio_streams
    
    def isActive(self, call_sid):
        return call_sid in self.live_audio_streams
    
    def stream_microphone(self):
        CHANNELS = 1
        SAMPLE_RATE = 44100
        CHUNK = 1024
        BYTES_PER_SAMPLE = 2  # assuming 16-bit audio

        """Generator function that captures audio and yields it."""
        wav_header = genHeader(SAMPLE_RATE, 16, CHANNELS)
        stream = audio.open(format=FORMAT, channels=CHANNELS,
                            rate=SAMPLE_RATE, input=True,
                            frames_per_buffer=CHUNK)


        yield wav_header  # Send the WAV header first
        while True:
            data = stream.read(CHUNK, exception_on_overflow=False)
            yield data



def parse_wave_header(header):  
    # Unpack the header using the correct format
    chunk_id, chunk_size, format = struct.unpack('<4sI4s', header[:12])
    subchunk1_id, subchunk1_size, audio_format, num_channels, sample_rate, byte_rate, block_align, bits_per_sample = struct.unpack('<4sIHHIIHH', header[12:36])
    subchunk2_id, subchunk2_size = struct.unpack('<4sI', header[36:44])
    
    # Convert bytes to strings where applicable
    chunk_id = chunk_id.decode('utf-8')
    format = format.decode('utf-8')
    subchunk1_id = subchunk1_id.decode('utf-8')
    subchunk2_id = subchunk2_id.decode('utf-8')
    
    # Create a dictionary to hold the metadata
    metadata = {
        "Chunk ID": chunk_id,
        "Chunk Size": chunk_size,
        "Format": format,
        "Subchunk1 ID": subchunk1_id,
        "Subchunk1 Size": subchunk1_size,
        "Audio Format": audio_format,
        "Num Channels": num_channels,
        "Sample Rate": sample_rate,
        "Byte Rate": byte_rate,
        "Block Align": block_align,
        "Bits Per Sample": bits_per_sample,
        "Subchunk2 ID": subchunk2_id,
        "Subchunk2 Size": subchunk2_size,
    }
    return metadata

def modify_wave_file_size(header, new_size):
    # Ensure the header is at least 44 bytes long
    if len(header) < 44:
        raise ValueError("Header is too short to contain a valid WAV header.")
    
    # Unpack the first part of the header, up to Subchunk2 Size
    first_part = header[:40]
    
    # Unpack the last part of the header, if there's anything beyond Subchunk2 Size
    last_part = header[44:]
    
    # Pack the new Subchunk2 Size into bytes (using little-endian unsigned int format)
    new_subchunk2_size_bytes = struct.pack('<I', new_size)
    
    # Reconstruct the header with the modified Subchunk2 Size
    modified_header = first_part + new_subchunk2_size_bytes + last_part
    
    return modified_header

def bytes_back(seconds, header):
    return int (seconds * header['Sample Rate']  * header['Num Channels'] * (header['Bits Per Sample']/8))

def genHeader(sampleRate, bitsPerSample, channels):
    datasize = 2000*10**6
    o = bytes("RIFF",'ascii')                                               # (4byte) Marks file as RIFF
    o += (datasize + 36).to_bytes(4,'little')                               # (4byte) File size in bytes excluding this and RIFF marker
    o += bytes("WAVE",'ascii')                                              # (4byte) File type
    o += bytes("fmt ",'ascii')                                              # (4byte) Format Chunk Marker
    o += (16).to_bytes(4,'little')                                          # (4byte) Length of above format data
    o += (1).to_bytes(2,'little')                                           # (2byte) Format type (1 - PCM)
    o += (channels).to_bytes(2,'little')                                    # (2byte) Channel count
    o += (sampleRate).to_bytes(4,'little')                                  # (4byte) Sample rate
    o += (sampleRate * channels * bitsPerSample // 8).to_bytes(4,'little')  # (4byte) Byte rate
    o += (channels * bitsPerSample // 8).to_bytes(2,'little')               # (2byte) Block align
    o += (bitsPerSample).to_bytes(2,'little')                               # (2byte) Bits per sample
    o += bytes("data",'ascii')                                              # (4byte) Data Chunk Marker
    o += (datasize).to_bytes(4,'little')                                    # (4byte) Data size in bytes
    return o
