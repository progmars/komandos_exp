from silero_vad import load_silero_vad, read_audio, get_speech_timestamps

import matplotlib.pyplot as plt
import pandas as pd

INPUT_FILE = "dumps/long_input2.wav"

model = load_silero_vad()
wav = read_audio(INPUT_FILE)

# plotting the vaweform too
v = pd.DataFrame(wav.numpy())
v.plot()

speech_timestamps = get_speech_timestamps(
  wav,
  model,
  threshold=0.3,
  return_seconds=True,
  visualize_probs=True
)

print(speech_timestamps)
plt.show()