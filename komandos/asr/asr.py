
from collections import deque
from enum import Enum
import threading
import time
import numpy as np
import wave

MAX_OUT_QUEUE_LENGTH = 100 # 100 recognized fragments should be enough. Consumers will start dropping out if cannot catch up.
MAX_IN_QUEUE_LENGTH = 1000 # Audio fragments from input to accumulate, will drop out if cannot process.

#MODEL_DIR = "models"
#WHISPER_MODEL = "large-v3"
WHISPER_MODEL_PATH = "models/Systran--faster-whisper-large-v3"
# WHISPER_MODEL_PATH = "models/faster_CrisperWhisper" # bad for LV
WHISPER_MODEL_PATH = "models/whisper-small-lv" # loses parts of text for LV, wrong interpretations
WHISPER_MODEL_PATH = "models/progmars-whisper-small-lv-ct2/1000" 

# WHISPERX_BATCH_SIZE = 16 # reduce if low on GPU mem, does not matter for small speech fragments
INFERENCE_DEVICE = "cuda" # cpu or cuda
INFERENCE_COMPUTE_TYPE = "float16" # "float16" # "int8" for CPU or if low on GPU mem (may reduce accuracy)
VAD_SILENCE_MS = 300

class AsrStatus(Enum):
    INIT = 1
    READY = 2
    ERROR = 3
    PROCESSING = 4

class AutomaticSpeechRecognizer:
    """
    Wrapper around faster-whisper
    """
    def __init__(self, language="en", vocabulary=[], dump_debug_files=False):

        self.language = language
        self.vocabulary_str = " ".join(vocabulary)
        self.free_mode = False # to ignore vocab

        self.in_queue = deque(maxlen=MAX_OUT_QUEUE_LENGTH)

        self.model = None

        # keep some history for analysis  
        self.out_queue = deque(maxlen=MAX_IN_QUEUE_LENGTH)  
        self.speech_extractor = None

        # Subscribers: callables that accept one argument (the detected speech)
        self.subscribers = set()

        # Dispatcher thread that constantly consumes input blocks and
        # returns output blocks to subscribers.
        self.lock = threading.Lock()
        self.status = AsrStatus.INIT
        self.last_failure = None
        self.dispatcher = threading.Thread(target=self.dispatch_loop, daemon=True)

        self.had_drop = False

        #DEBUG counter
        self.dump_debug_files = dump_debug_files
        self.dump_block_ix = 0


    def set_free_mode(self, free_mode):
        with self.lock:
            self.free_mode = free_mode


    def subscribe(self, callback):
        """Subscribe a callable to receive detected text fragments or current status.
        
        The callback will be called as callback(text, status, failure) where 
        - text is one of the latest detected strings
        - status is AsrStatus
        - failure is optional explanation for ERROR status
        """
        with self.lock:
            self.subscribers.add(callback)


    def unsubscribe(self, callback):
        with self.lock:
            self.subscribers.discard(callback)


    def on_audio_arrived(self, block):
        # no point accumulating stale data too early
        # user needs to wait
        if self.status not in [AsrStatus.READY, AsrStatus.PROCESSING]:
            return
        # avoid spamming until recover
        if len(self.in_queue) >= MAX_IN_QUEUE_LENGTH and not self.had_drop:
            print("WARNING: Dropout detected, cannot catch up to incoming audio.")
            self.had_drop = True
        else:
            self.had_drop = False
        with self.lock:
            self.in_queue.append(block)


    def dispatch_loop(self):
        """Background loop that consumes audio blocks 
        and dispatches detected text to consumers."""
        while True:
            if not self.is_ready():
                time.sleep(0.01)
                continue

            with self.lock:
                block = self.in_queue.popleft() if self.in_queue else None

            if block is None:
                time.sleep(0.01)
                continue

            result = None
            try:
                result = self.process_input_block(block)
            except Exception as e:
                print(f"Detection error: {e}")
                pass

            if result is not None:
              self.out_queue.extend(result)

            # consume everything that was accumulated
            # to give subscribers a chance to catch up
            while True:
                text = self.out_queue.popleft() if self.out_queue else None
                if not text:
                    break                
                print(f"Extracted speech: {text}")
                self.notify_subscribers(text)
            
            # debug
            # time.sleep(10)


    def notify_subscribers(self, result):
        # Snapshot subscribers to avoid holding lock while calling them
        with self.lock:
            subs = list(self.subscribers)

        for cb in subs:
            try:
                cb(result)
            except Exception as e:
                # Protect dispatcher from exceptions in user callbacks
                print(f"Error in ASR subscriber callback: {e}")

# The main wrapping logic below

    def process_input_block(self, block):
        # self.dump_add_to_file(block)

        detections = []

        if self.dump_debug_files:
            self.dump_block_ix = self.dump_block_ix + 1            
            # self.dump_to_file(f"audio_pre_{self.dump_block_ix}", block)

        # a simple fragmenter to feed longer fragments to WhisperX
        # and then leave it to its internal VAD to deal with it properly
        self.speech_extractor.accumulate(block)

        while True:
            ready_fragment = self.speech_extractor.get_pending_voice_fragment()
            if ready_fragment is None:
                break

            if self.dump_debug_files:
                self.dump_block_ix = self.dump_block_ix + 1
                self.dump_to_file(f"speechfrags/audio_{self.dump_block_ix}", ready_fragment)
            
            if self.model:
                """ 
                For WhisperX
                result = self.model.transcribe(ready_fragment, batch_size=WHISPERX_BATCH_SIZE, 
                                            to_streaming=True,
                                            chunk_size = 30,
                                            dump_file_ix=self.dump_block_ix)
                
                for element in result: 
                    print(element)
                    detections.append(element)
                """
                """
                Hotwords are great, but they limit Whisper to not detect sentences anymore.
                So we disable them dynamically as needed.
                """

                hotwords = self.vocabulary_str if not self.free_mode else None

                """
                with internal VAD
                segments, _ = self.model.transcribe(ready_fragment,
                            language=self.language, 
                            vad_filter=True,
                            vad_parameters=dict(min_silence_duration_ms=VAD_SILENCE_MS),
                            hotwords=hotwords)
                """
                # with our own Silero VAD only
                segments, _ = self.model.transcribe(ready_fragment,
                            language=self.language, 
                            vad_filter=False,
                            hotwords=hotwords)
                
                segments = list(segments)
                joined = " ".join(x.text for x in segments)
                # redundant space - usually detections start with space
                detections.append(joined)
                

        # DEBUG
        # char_set = string.ascii_lowercase + string.ascii_uppercase
        # s = "".join(random.sample(char_set*6, random.randrange(6, 10)))

        # return s
        return detections


    def dump_to_file(self, name, block):
        dumpf = f"dumps/asr/{name}.wav"
        wf = wave.open(dumpf, "wb")
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(16000)                
        wavblock = (block * 32768).astype(np.int16)
        wf.writeframesraw(wavblock.tobytes())
        wf.close()


    def boot(self):
        # to not occupy the calling thread, so that UI is free to load
        t = threading.Thread(target=self.load_models, daemon=True)
        t.start()

        self.dispatcher.start()


    def load_models(self):
        try:
            # intentionally here and not at the start of the file
            # because ctranslate2\__init__.py is heavy and loads stuff
            # so we want it be part of the boot sequence
            # to not stall the main UI thread during import
            from faster_whisper import WhisperModel
            from .silero_speech_extractor import SileroSpeechExtractor
            self.speech_extractor = SileroSpeechExtractor()
            
            # DEBUG
            # return
            # raise Exception('spam', 'eggs')
            """
            Interesting params to consider:
            https://whisper-api.com/docs/transcription-options/
            https://github.com/openai/whisper/discussions/117#discussioncomment-3727051
            prompt (alias initial_prompt) conditions the model on the text 
            that appeared in the previous ~30 seconds of audio,
            and in long-form transcription it helps continuing the text in a consistent style,
            e.g. starting a sentence with a capital letter if the previous context ended 
            with a period. 
            You can also use this for "prompt engineering", to inform the model
            to become more likely to output certain jargon (" So we were just talking about DALL·E") 
            CAVEAT: The Whisper very frequently hallucinates when provided with a prompt
            prefix accepts a partial transcription for the current audio input,
            allowing for resuming the transcription after a certain point 
            within the 30-second speech.
            It's useful to prototype semi-realtime transcription, 
            where overlapping windows would be used to incrementally accept audio
            every second or so, and prefix could contain the text for the overlapping portion.
            hotwords - faster-whisper specific
            "return_timestamps": True is said to reduce hallucinations
            "without_timestamps": True,
            "max_initial_timestamp": 0.0,
            "word_timestamps": False,

            Another interesting option is using calibration for specific user's voice:
            https://github.com/ggml-org/whisper.cpp/discussions/190
            """
            asr_options = { 
                # hotwords help best, use ones collected by CommandDispatcher
                # but not sure what is the difference from initial_prompt -
                # both work the same, but someone suggested to use hotwords better
                "hotwords": self.vocabulary_str,
                # prefix glitches, repeats itself and no other text.
                # "prefix": "Jā, tik tiešām.",
                # initial_prompt helps noticeably
                # "initial_prompt": " ".join(self.vocabulary),
                # patience sometimes helps, but can get stuck if too large
                # "patience": 1
                # did not notice major effects from these
                # "without_timestamps": False # maybe not supported in WhisperX
                # "best_of": 5,
                # "beam_size": 5 # did not notice major effect
            }

            """ 
            
            self.model = whisperx.load_model(WHISPER_MODEL, INFERENCE_DEVICE, vad_method="silero", 
                                        asr_options=asr_options,
                                        compute_type=INFERENCE_COMPUTE_TYPE, download_root=MODEL_DIR,
                                        language=self.language)
            """
            self.model = WhisperModel(model_size_or_path=WHISPER_MODEL_PATH, device=INFERENCE_DEVICE,
                                        compute_type=INFERENCE_COMPUTE_TYPE, local_files_only=True)

            self.status = AsrStatus.READY
        except Exception as e:
            self.model = None
            failure = f"Failed to initialize speech recognizer: {e}"
            self.last_failure = failure            
            self.status = AsrStatus.ERROR
            print(failure)
            # quit, cannot continue the thread loop
            return

    
    def is_ready(self):
        return self.model is not None


    def get_last_failure_reason(self):
        return self.last_failure


    # just to be compatible with start/stop "interface"
    def shut_down(self):
        pass

     