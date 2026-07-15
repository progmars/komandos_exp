import numpy as np
import wave
import sys
import sys
# for importing SileroSpeechExtractor from a parallel folder
sys.path.append("")
from komandos.asr.silero_speech_extractor import SileroSpeechExtractor

SAMPLE_RATE = 16000
BLOCK_SIZE_MS = 32
BLOCK_SIZE_SAMPLES = SAMPLE_RATE // 1000 * BLOCK_SIZE_MS

sse = SileroSpeechExtractor()
wf = wave.open("dumps/putns2_input.wav", "rb")

nframes = wf.getnframes()
raw = wf.readframes(nframes)
wf.close()

# Convert raw bytes to numpy float32 in range -1..1
# Assume int16 mono
dtype = np.int16
data = np.frombuffer(raw, dtype=dtype).astype(np.float32) / 32768.0

total = data.shape[0]

pos = 0
block_size = BLOCK_SIZE_SAMPLES
block_duration = (BLOCK_SIZE_SAMPLES / float(SAMPLE_RATE))

voiced_seg_start = None

while True:
    end = pos + BLOCK_SIZE_SAMPLES
    if end <= total:
        chunk = data[pos:end]
    else:
        break

    pos = end    

    block = chunk
    time_pos = pos // BLOCK_SIZE_SAMPLES * BLOCK_SIZE_MS
    
    res = sse.accumulate(chunk)

    if res:
        if voiced_seg_start is None:
            voiced_seg_start = pos - BLOCK_SIZE_SAMPLES
    else:
        # end of successful run
        if voiced_seg_start is not None:
            print(f"{voiced_seg_start} - {pos - BLOCK_SIZE_SAMPLES}: TRUE")
            voiced_seg_start = None


i = 0
while True:
    i += 1
    f = sse.get_pending_voice_fragment()

    if f is None:
        exit(0)
    
    dumpf = f"dumps/asr/speechfrags/silero_fragmenter{i}.wav"
    wf = wave.open(dumpf, "wb")
    wf.setnchannels(1)
    wf.setsampwidth(2)  # 16-bit
    wf.setframerate(16000)                
    wavblock = (f * 32768).astype(np.int16)
    wf.writeframesraw(wavblock.tobytes())
    wf.close()
