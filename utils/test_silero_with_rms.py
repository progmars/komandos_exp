import numpy as np
import wave
import torch
from silero_vad import load_silero_vad, read_audio, get_speech_timestamps

SAMPLE_RATE = 16000
BLOCK_SIZE_MS = 32 # the best for realtime with Silero VAD
BLOCK_SIZE_SAMPLES = SAMPLE_RATE // 1000 * BLOCK_SIZE_MS
VOICE_AMPLITUDE_THRESHOLD = 0.05 # To ignore noise
SILERO_VAD_THRESHOLD = 0.3
VOCAL_FREQS = [50, 1000]  # Frequency range to detect sounds that could be speech

vad_model = load_silero_vad()

# more direct method to avoid timestamping overhead
# when processing single small chunks and don't care about speech locations
def get_silero_prob(chunk):
    tensor = torch.from_numpy(chunk)
    prob = vad_model(tensor, SAMPLE_RATE).item()
    # important for longer inputs!
    vad_model.reset_states()
    return prob
 
def is_in_voice_range(chunk):
    freq = (
        np.argmax(np.abs(np.fft.rfft(chunk)))
        * SAMPLE_RATE
        / BLOCK_SIZE_SAMPLES
    )

    is_in_range = VOCAL_FREQS[0] <= freq <= VOCAL_FREQS[1]
    return is_in_range

torch.set_printoptions(precision=3,sci_mode=False)

wf = wave.open("dumps/lapas2.wav", "rb")
nframes = wf.getnframes()
raw = wf.readframes(nframes)
wf.close()

# Convert raw bytes to numpy float32 in range -1..1
# File is int16 mono
data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
total = data.shape[0]

tensor = torch.from_numpy(data)

predicts = vad_model.audio_forward(tensor, sr=SAMPLE_RATE)
# print(predicts)


pos = 0
block_size = BLOCK_SIZE_SAMPLES
block_duration = (block_size / float(SAMPLE_RATE))

while True:
    end = pos + block_size
    if end <= total:
        chunk = data[pos:end]
    else:
        break

    pos = end    

    time_pos = pos // BLOCK_SIZE_SAMPLES * BLOCK_SIZE_MS
    rms = np.sqrt(np.mean(chunk * chunk))
    has_enough_volume = rms >= VOICE_AMPLITUDE_THRESHOLD

    prob = get_silero_prob(chunk)
    has_voice = prob >= SILERO_VAD_THRESHOLD
    is_in_range = is_in_voice_range(chunk)

    #if has_enough_volume:
    print(f"{time_pos}: RMS: {rms:.2f} {has_enough_volume}; Silero VAD: {prob:.2f} {has_voice}") #; Is in freq range: {is_in_range}")

