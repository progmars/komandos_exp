import numpy as np
import wave
import torch
import matplotlib
import matplotlib.pylab as plt
from silero_vad import load_silero_vad, read_audio, get_speech_timestamps

# just refreshing my Python slicing knowledge
arr = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
print(arr[:-6])
leftover_ix = len(arr) - 6
print(arr[leftover_ix:])



INPUT_FILE = "dumps/long_input2.wav"
SAMPLE_RATE = 16000
BLOCK_SIZE_SAMPLES = 512 # to match Silero VAD defaults, 32ms buffer

vad_model = load_silero_vad()

# read by 32ms chunks and feed manually to simulate audio input
wf = wave.open(INPUT_FILE, "rb")
nframes = wf.getnframes()
raw = wf.readframes(nframes)
wf.close()

# Convert raw bytes to numpy float32 in range -1..1
# The test file is known to be int16 mono 16kHZ
wav = np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0

total = wav.shape[0]
pos = 0

voiced_confidences_no_reset = []

while True:
    end = pos + BLOCK_SIZE_SAMPLES
    if end <= total:
        chunk = wav[pos:end]
    else:
        break
    pos = end    

    # as in pyaudio-streaming-examples.ipynb
    new_confidence = vad_model(torch.from_numpy(chunk), SAMPLE_RATE).item()
    voiced_confidences_no_reset.append(new_confidence)

#========================
# reset once before the test with resets in the loop
vad_model.reset_states()
pos = 0

voiced_confidences_with_reset = []

chunk_count = 0

while True:
    end = pos + BLOCK_SIZE_SAMPLES
    if end <= total:
        chunk = wav[pos:end]
    else:
        break
    pos = end    

    chunk_count += 1

    # as in pyaudio-streaming-examples.ipynb
    new_confidence = vad_model(torch.from_numpy(chunk), SAMPLE_RATE).item()
    voiced_confidences_with_reset.append(new_confidence)

    # important - this makes the results much better in this case
    if chunk_count > 312: # every 10 seconds
        print("resetting")
        chunk_count = 0
        vad_model.reset_states()


#========================
# reset once before the test with resets in the loop
vad_model.reset_states()
pos = 0

voiced_confidences_with_always_reset = []

while True:
    end = pos + BLOCK_SIZE_SAMPLES
    if end <= total:
        chunk = wav[pos:end]
    else:
        break
    pos = end    

    # as in pyaudio-streaming-examples.ipynb
    new_confidence = vad_model(torch.from_numpy(chunk), SAMPLE_RATE).item()
    voiced_confidences_with_always_reset.append(new_confidence)

    vad_model.reset_states()

#------------------------
# plot the confidences for the speech
plt.figure(figsize=(10,4))
plt.plot(voiced_confidences_with_reset)
plt.figure(figsize=(10,4))
plt.plot(voiced_confidences_no_reset)
plt.figure(figsize=(10,4))
plt.plot(voiced_confidences_with_always_reset)
plt.figure(figsize=(10,4))
plt.plot(wav)
plt.show()

