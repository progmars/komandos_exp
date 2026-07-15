import sounddevice as sd
import numpy as np
from audio.constants import *

BLOCK_SIZE_SAMPLES = SAMPLE_RATE // 1000 * BLOCK_SIZE_MS

MAX_QUEUE_LENGTH = 100 # About 5 seconds should be enough. Consumers will start dropping out if cannot catch up.


class Output:

    def __init__(self):
        pass


    def enumerate_devices(self):
        best_output_devices = []

        hostapis = sd.query_hostapis()
        devices = sd.query_devices()
        # try to select the best API
        # on Windows, the priority is DirectSound,WASAPI,MME
        # DirectSound - because WASAPI throws errors with samplerate 16k
        # no ASIO though, too exotic anyway
        # for Linux and MAC just use the first default

        priorities = ["DirectSound","WASAPI", "MME"]
        chosen = None
        for pname in priorities:
            for h in hostapis:
                name = h.get("name", "")
                if pname.lower() in name.lower():
                    desired_hostapi_devices = h.get("devices", [])
                    chosen = name
                    break
            if chosen:
                break

        if not chosen and hostapis:
            # fallback to the first available hostapi
            desired_hostapi_devices = hostapis[0].get("devices", [])
            chosen = hostapis[0].get("name", "<unknown>")

        print(f"Selected hostapi: {chosen}, devices: {desired_hostapi_devices}")

        for idx, dev in enumerate(devices):
            # filter output devices only
            # problem - they will be duplicated by hostapis
            # the default hostapi also has cropped names
            dev_max_out = dev.get("max_output_channels", 0)
            dev_index = dev.get("index", idx)
            # Include device only if it has input channels and this device's index is present in the chosen hostapi's devices.
            if dev_max_out > 0 and dev_index in desired_hostapi_devices:
                best_output_devices.append(dev)

        return best_output_devices


    def play(self, np_array, sample_rate):
        print("Playing...")
        # device=idx, keep default for now
        sd.play(np_array, samplerate=sample_rate)