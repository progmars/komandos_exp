CHANNELS = 1
SAMPLE_RATE = 16000 # as required by Whisper and Silero VAD
# Block size in milliseconds
BLOCK_SIZE_MS = 32
# Important:
# Silero VAD model was trained using 512, 1024, 1536 samples for 16000
# 32ms 64ms 96ms
# It will chunk by 32ms probs for 16kHz, so we better use the same size
# for the best efficiency.

