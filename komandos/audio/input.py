import sounddevice as sd
import threading
import time
from collections import deque
import numpy as np
import wave
from audio.constants import *

BLOCK_SIZE_SAMPLES = SAMPLE_RATE // 1000 * BLOCK_SIZE_MS

MAX_QUEUE_LENGTH = 100 # About 5 seconds should be enough. Consumers will start dropping out if cannot catch up.

DEBUG_IN_WAV_DEVID = -404

class Input:
    """
    Streaming buffer that collects incoming audio blocks from sounddevice.
    """
    def __init__(self, boost, record_input_dump_file=False, add_input_wav_simulator_device=False):
        self.buffer = deque(maxlen=MAX_QUEUE_LENGTH)
        self.stream = None
        self.add_input_wav_simulator_device = add_input_wav_simulator_device
        self.is_recording = False
        self.last_failure = None
        self.boost = boost
        # Debug: path to a local file to append boosted blocks
        self.input_dump_file = "dumps/input.wav" if record_input_dump_file else None
        self.simulation_input_wav_file = "dumps/long_input.wav" if add_input_wav_simulator_device else None
        # debug_wave is a wave.Wave_write instance when debugging is active
        self.debug_wave = None
        # Subscribers: callables that accept one argument (the audio block)
        self.subscribers = set()

        # Dispatcher thread that constantly consumes buffered blocks and
        # forwards them to subscribers.
        self.lock = threading.Lock()        
        self.data_available = threading.Condition(self.lock)
        self.dispatcher = threading.Thread(target=self.dispatch_loop, daemon=True)
        self.dispatcher.start()

        # Simulation controls (for feeding WAV files instead of real device)
        self.simulation_thread = None
        self.simulation_stop = threading.Event()


    def enumerate_devices(self):
        best_input_devices = []

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
            # filter input devices only
            # problem - they will be duplicated by hostapis
            # the default hostapi also has cropped names
            dev_max_in = dev.get("max_input_channels", 0)
            dev_index = dev.get("index", idx)
            # Include device only if it has input channels and this device's index is present in the chosen hostapi's devices.
            if dev_max_in > 0 and dev_index in desired_hostapi_devices:
                best_input_devices.append(dev)
        
        if self.add_input_wav_simulator_device:
            best_input_devices.append({ "name": "Simulator from dumps/Recording.wav", "index": DEBUG_IN_WAV_DEVID })

        return best_input_devices


    def set_boost(self, boost):
        self.boost = boost


    def subscribe(self, callback):
        """Subscribe a callable to receive audio blocks.

        The callback will be called as callback(block) where block is a numpy
        array containing the recorded samples.
        """
        with self.lock:
            self.subscribers.add(callback)


    def unsubscribe(self, callback):
        with self.lock:
            self.subscribers.discard(callback)


    def start_recording(self, device_id):
        self.shut_down()

        # Open debug file before starting the stream so callback can write
        # immediately if it fires on start.
        if self.input_dump_file:
            try:
                # Create/truncate WAV file and write header via wave module
                wf = wave.open(self.input_dump_file, "wb")
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(SAMPLE_RATE)
                self.debug_wave = wf
            except Exception as e:
                # Non-fatal: surface error but continue without debug file
                print(f"Failed to open debug WAV file {self.input_dump_file}: {e}")

        if device_id == DEBUG_IN_WAV_DEVID:
            self.start_wav_simulation()
            return

        try:
            self.stream = sd.InputStream(
                device=device_id,
                channels=CHANNELS,
                samplerate=SAMPLE_RATE,
                # accept the default float32 with -1 +1 limits
                # to avoid dealing with magic 32768
                # dtype=np.int16,
                blocksize=BLOCK_SIZE_SAMPLES,
                callback=self.callback,
            )

            self.stream.start()
            self.is_recording = True
        except Exception as e:
            failure = f"Failed to initialize audio input: {e}"
            self.last_failure = failure
            # Ensure we leave the object in a clean state
            if self.stream is not None:
                try:
                    self.stream.close()
                except Exception:
                    pass
                self.stream = None
            # Close debug wave file on failure to start
            if self.debug_wave is not None:
                try:
                    self.debug_wave.close()
                except Exception:
                    pass
                self.debug_wave = None
            self.is_recording = False
            # propagate exception so caller (UI) can show an error
            raise


    def shut_down(self):
        with self.data_available:
            self.is_recording = False
            self.data_available.notify_all()

        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        # Stop any running WAV simulation
        self.stop_simulation()

        # Close debug file if open
        if self.debug_wave is not None:
            try:
                self.debug_wave.close()
            except Exception:
                pass
            self.debug_wave = None


    def get_next_consumable(self):
        with self.data_available:
            if not self.buffer:
                waited = self.data_available.wait()
                if not waited and not self.buffer:
                    return None

            if self.buffer:
                return self.buffer.popleft()
            return None


    def callback(self, indata, _frames, _time, status):
        if not self.is_recording:
            return

        # sounddevice callback runs in a separate thread
        if status:
            # Surface stream status for debugging; do not raise here
            print(f"Input stream status: {status}")

        # Ensure we store a copy of the data
        try:
            # indata is a numpy array -1,1
            # and it is an array of arrays, so need to flatten to make 1 channel
            
            # Apply microphone boost here so subscribers receive boosted audio.
            # Work on a copy.
            block = indata.flatten().copy()
            boost = self.boost

            if boost != 0:
                factor = 1.0 + (boost / 100.0)
                # multiply, clip to -1,1 range
                tmp = block * factor
                tmp = np.clip(tmp, -1, 1)
                block = tmp

            self.dump_to_file(block)

            with self.data_available:
                self.buffer.append(block)
                # notify consumer thread
                self.data_available.notify()
        except Exception as e:
            # Do not let exceptions in callback crash the stream thread; print for debugging.
            print(f"Error in input callback: {e}")


    def dump_to_file(self, block):

        # If debug file is enabled, append raw bytes of the boosted block.
        wf = self.debug_wave
        if wf is not None:
            try:
                # convert
                wavblock = (block * 32768).astype(np.int16)
                wf.writeframesraw(wavblock.tobytes())
            except Exception as e:
                # Print for debugging but do not raise in callback
                print(f"Failed to write debug block: {e}")


    def dispatch_loop(self):
        """Background loop that consumes audio blocks and dispatches them to subscribers."""
        while True:
            # yield a bit to not use the entire CPU core time
            time.sleep(0.0001)

            block = self.get_next_consumable()
            if block is None:
                continue

            # Snapshot subscribers to avoid holding lock while calling them
            with self.lock:
                subs = list(self.subscribers)

            for cb in subs:
                try:
                    cb(block)
                except Exception as e:
                    # Protect dispatcher from exceptions in user callbacks
                    print(f"Error in subscriber callback: {e}")


    def start_wav_simulation(self):
        """Start feeding audio from a WAV file into the input callback.

        wav_path: path to WAV file (any PCM WAV)
        loop: whether to loop the file indefinitely
        speed: playback speed multiplier (1.0 = real time)

        This runs in a background thread. If a real input stream is open,
        this will raise an Exception.
        """        
        if self.stream is not None:
            raise RuntimeError("Cannot start WAV simulation while real input stream is open")

        loop = False
        speed = 1.0

        # Stop any previous simulation
        self.stop_simulation()

        # Clear stop flag and mark as recording so callback() processes blocks
        self.simulation_stop.clear()

        def sim_loop():
            try:
                wf = wave.open(self.simulation_input_wav_file, "rb")
            except Exception as e:
                print(f"Failed to open WAV for simulation: {e}")
                self.is_recording = False
                return

            try:
                nframes = wf.getnframes()
                raw = wf.readframes(nframes)
                wf.close()

                # Convert raw bytes to numpy float32 in range -1..1
                # Assume int16 mono
                dtype = np.int16
                data = np.frombuffer(raw, dtype=dtype).astype(np.float32) / 32768.0

                # Now iterate over blocks and feed to callback
                total = data.shape[0]
                pos = 0
                block_size = BLOCK_SIZE_SAMPLES
                block_duration = (block_size / float(SAMPLE_RATE)) / max(1e-6, speed)

                while not self.simulation_stop.is_set():
                    if pos >= total:
                        if loop:
                            pos = 0
                        else:
                            break

                    end = pos + block_size
                    if end <= total:
                        chunk = data[pos:end]
                    else:
                        # last partial block: pad with zeros
                        chunk = np.zeros(block_size, dtype=np.float32)
                        remaining = max(0, total - pos)
                        if remaining > 0:
                            chunk[:remaining] = data[pos:pos + remaining]

                    pos = end

                    # Call callback directly. Provide frames and placeholders for time/status.
                    try:
                        self.callback(chunk, BLOCK_SIZE_SAMPLES, None, None)
                    except Exception as e:
                        print(f"Error in WAV simulation callback: {e}")

                    # Sleep to emulate real-time playback
                    time.sleep(block_duration)

            finally:
                # simulation finished
                self.is_recording = False

        self.simulation_thread = threading.Thread(target=sim_loop, daemon=True)
        self.simulation_thread.start()

        self.is_recording = True


    def stop_simulation(self):
        if self.simulation_thread is None:
            return

        # Signal stop and join
        self.simulation_stop.set()
        thr = self.simulation_thread
        self.simulation_thread = None

        thr.join(timeout=1.0)

        # Ensure flag cleared
        self.simulation_stop.clear()


    def is_ready(self):
        return self.is_recording


    def get_last_failure_reason(self):
        return self.last_failure

