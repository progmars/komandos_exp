import whisperx
import wave
import sys
import pyaudio
import numpy as np

p = pyaudio.PyAudio()
for i in range(p.get_device_count()):
    print (p.get_device_info_by_index(i)["name"])
quit()

'''
# whisper needs pcm_s16le PCM signed 16-bit little-endian, 1 channel
# A NumPy array containing the audio waveform, in float32 dtype.
# np.frombuffer(out, np.int16).flatten().astype(np.float32) / 32768.0
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
SAMPLE_RATE = 16000
RECORD_SECONDS = 5

stream = p.open(format=FORMAT, channels=CHANNELS, rate=SAMPLE_RATE, input=True,input_device_index=1)
# frames_per_buffer=FRAMES_PER_BUFFER,

with wave.open('output.wav', 'wb') as wf:
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(p.get_sample_size(FORMAT))
    wf.setframerate(SAMPLE_RATE)
    
    print('Recording...')
    for _ in range(0, SAMPLE_RATE // CHUNK * RECORD_SECONDS):
        wf.writeframes(stream.read(CHUNK))
    print('Done')

    stream.close()
    p.terminate()
    
quit()
'''

device = "cpu" # cuda
audio_file = "samples/retv_short.pcm"
# audio_file = "output.wav"
batch_size = 16 # reduce if low on GPU mem
compute_type = "int8"
language = "lv"
#compute_type = "float16" # change to "int8" if low on GPU mem (may reduce accuracy)

# 1. Transcribe with original whisper (batched)
# Only large-v3 can handle Latvian
# save model to local path (optional)
model_dir = "models"
# they say, silero is better for realtime
model = whisperx.load_model("large-v3", device, vad_method="silero", compute_type=compute_type, download_root=model_dir, language=language)

# audio = whisperx.load_audio(audio_file)

with open(audio_file, 'rb') as file:
    byte_array = bytearray(file.read())
    
audio = np.frombuffer(byte_array, np.int16).flatten().astype(np.float32) / 32768.0

result = model.transcribe(audio, batch_size=batch_size, to_streaming=True)
for element in result: 
    print(element)

# for non-streaming
# print(result["segments"]) # before alignment
