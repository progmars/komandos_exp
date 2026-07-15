from silero_vad import load_silero_vad, read_audio, get_speech_timestamps
SAMPLING_RATE = 16000

vad_model = load_silero_vad()
wav = read_audio("dumps/s.wav", 
                    sampling_rate=SAMPLING_RATE)
# chunk size is 32 ms, and each second of the audio contains 31.25 chunks
# currently only chunks of size 512 are used for 16 kHz and 256 for 8 kHz
# e.g. 512 / 16000 = 256 / 8000 = 0.032 s = 32.0 ms
predicts = vad_model.audio_forward(wav, sr=SAMPLING_RATE)
print(predicts)
speech_timestamps = get_speech_timestamps(wav, 
                vad_model,
                return_seconds=True)
print(speech_timestamps)

