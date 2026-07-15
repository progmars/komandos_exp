import numpy as np
import wave
import torch
import matplotlib
import matplotlib.pylab as plt
from silero_vad import load_silero_vad, read_audio, get_speech_timestamps

INPUT_FILE = "dumps/long_input.wav"
SAMPLE_RATE = 16000
BLOCK_SIZE_MS = 32 # to match Silero VAD
BLOCK_SIZE_SAMPLES = SAMPLE_RATE // 1000 * BLOCK_SIZE_MS

vad_model = load_silero_vad()

torch.set_printoptions(precision=3,sci_mode=False)

ra_wav_tensor = read_audio(INPUT_FILE, 
                sampling_rate=SAMPLE_RATE)
predicts = vad_model.audio_forward(ra_wav_tensor, sr=SAMPLE_RATE)
print(predicts)

# now read by 32ms chunks and feed manually

wf = wave.open(INPUT_FILE, "rb")
nframes = wf.getnframes()
raw = wf.readframes(nframes)
wf.close()


# Convert raw bytes to numpy float32 in range -1..1
# File is int16 mono
wav = np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0
# print(wav)

wav_tensor = torch.from_numpy(wav)
# print(wav_tensor)

predicts = vad_model.audio_forward(wav_tensor, sr=SAMPLE_RATE)
print(predicts)


# now by single block
total = wav.shape[0]

pos = 0
block_size = BLOCK_SIZE_SAMPLES
block_duration = (block_size / float(SAMPLE_RATE))

while True:
    if pos >= total:
        break

    end = pos + block_size
    if end <= total:
        chunk = wav[pos:end]
    else:
        break

    pos = end    

    time_pos = pos // BLOCK_SIZE_SAMPLES * BLOCK_SIZE_MS
    tensor = torch.from_numpy(chunk)
    prob1 = vad_model.audio_forward(tensor, SAMPLE_RATE).item()
    prob2 = vad_model(tensor, SAMPLE_RATE).item()

    print(f"{time_pos}: Silero VAD: {prob1:.2f}  {prob2:.2f}")

