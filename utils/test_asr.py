import numpy as np
import wave
import sys
# for importing AutomaticSpeechRecognizer from a parallel folder
sys.path.append("")
from komandos.asr.asr import AutomaticSpeechRecognizer

asr = AutomaticSpeechRecognizer("lv")
asr.load_models()

file_path = "dumps/piedalos_ara.wav"
file_path = "dumps/nepatik.wav"

wf = wave.open(file_path, "rb")

nframes = wf.getnframes()
raw = wf.readframes(nframes)
wf.close()

# Convert raw bytes to numpy float32 in range -1..1
# Assume int16 mono
dtype = np.int16
data = np.frombuffer(raw, dtype=dtype).astype(np.float32) / 32768.0

segments, _ = asr.model.transcribe(data,
                            language=asr.language, 
                            vad_filter=False,
                            hotwords=[])
segments = list(segments)
for segment in segments:
    print(segment.text)

joined = "".join(x.text for x in segments)
print(joined)
