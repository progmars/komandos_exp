from collections import deque
import numpy as np
import torch
from silero_vad import load_silero_vad

try:
    # for running from outer tests
    from ..audio.constants import *
except Exception:
    from audio.constants import *

# Important:
# Silero VAD models were trained using 512, 1024, 1536 samples for 16000
# 32ms 64ms 96ms.

# This logic assumes 32ms and might break with larger buffers.

MIN_SILENCE_WAIT_BLOCKS = 1000 // BLOCK_SIZE_MS  # 1000ms for slow speakers
MAX_PENDING_VOICE_BLOCKS = 30000 // BLOCK_SIZE_MS  # 30s

# Silero sometimes misses consonant start/end, 
# so add small tails to prepend/append small buffers.
# OpenAI forum suggests adding 300ms as pre/post.
# PRE_TAIL_BLOCKS should be smaller than MIN_SILENCE_WAIT_BLOCKS.
PRE_TAIL_BLOCKS = 300 // BLOCK_SIZE_MS

SILERO_VAD_THRESHOLD = 0.3 # found experimentally, better detects consonants
VOICE_AMPLITUDE_THRESHOLD = 0.05 # To ignore noise; reasonable RMS value

# silero can last about 30 seconds without reset
# then it breaks down and does not fully recover always
# 10 seconds seem to work reasonably well
SILERO_RESET_EVERY_CHUNKS = 10000 // BLOCK_SIZE_MS

# ---------------
# Just some precalculations to avoid them every loop
REMOVE_FROM_TAIL = MIN_SILENCE_WAIT_BLOCKS - PRE_TAIL_BLOCKS



# There was also idea to use
# VOCAL_FREQS = [50, 1000]  # Frequency range to detect sounds that could be speech
# but turned out not helpful to combine with Silero+RMS at all

class SileroSpeechExtractor:
    """Speech fragmenter using Silero VAD.
    """
    def __init__(self):
        # queues of audio blocks (numpy arrays)
        self.current_voice_blocks = deque(maxlen=MAX_PENDING_VOICE_BLOCKS)
        self.completed_fragments = deque(maxlen=100000)

        self.consecutive_silent_blocks = 0
        # look-behind buffer to collect silent blocks that we skipped
        # the limit will let us consume the entire deque without counting
        # any indexes
        self.prefix_blocks = deque(maxlen=PRE_TAIL_BLOCKS)

        # instantiate Silero VAD model using provided loader
        # loader returns a jit/onnx-wrapped model compatible with utils.get_speech_timestamps
        self.vad_model = load_silero_vad()

        self.silero_reset_chunk_counter = 0


    def has_voice(self, block):
        self.silero_reset_chunk_counter += 1
        # Use the model's faster frame-level predictions instead of full
        # get_speech_timestamps.
        tensor = torch.from_numpy(block.astype(np.float32))
        prob = self.vad_model(tensor, SAMPLE_RATE).item()

        has_voice = prob >= SILERO_VAD_THRESHOLD

        rms = np.sqrt(np.mean(block * block))
        has_enough_volume = rms >= VOICE_AMPLITUDE_THRESHOLD
        # print(f"RMS: {rms:.2f} {has_enough_volume}; Silero VAD: {max_prob:.2f} {has_voice}")

        return has_voice and has_enough_volume


    def reset_silero(self, force=False):
        if force or self.silero_reset_chunk_counter >= SILERO_RESET_EVERY_CHUNKS:
            # not sure how often we should call it
            # but if we don't, it stops detecting after a while
            # however, calling it every chunk also hurts performance
            # experimentally, it seems 10 seconds or every commit event works best
            self.vad_model.reset_states()
            self.silero_reset_chunk_counter = 0


    def accumulate(self, block):
        """Process an incoming block and assemble speech fragments.

        - When voice is detected, start a fragment immediately
          (might lead to false positives but it's better than missing blocks).
          Then continue the fragment with all incoming blocks.
        - When silence persists for MIN_SILENCE_WAIT_BLOCKS, commit fragment, 
          but leave only PRE_TAIL_BLOCKS of the silence in it. 
        - When fragment reaches MAX_PENDING_VOICE_BLOCKS, commit immediately.
        - When starting a fragment, prepend the recent silent look-behind buffer
          but only the last PRE_TAIL_BLOCKS of the look-behind.
        """
        voice_detected = self.has_voice(block)
        # return voice_detected

        if voice_detected:
            if len(self.current_voice_blocks) == 0:
                # We were not yet assembling a fragment.
                # Start a fragment by prepending up to PRE_TAIL_BLOCKS of
                # preceding silence.
                # The deque is limited to PRE_TAIL_BLOCKS, so we can add it all.               
                # print(f"Prepending silence {len(self.prefix_blocks)}")
                self.current_voice_blocks.extend(self.prefix_blocks)

                # we've consumed the buffer
                self.prefix_blocks.clear()

            # Add the voiced block itself.
            self.current_voice_blocks.append(block)
            
            # print(f"Added a voice block {len(self.current_voice_blocks)}")
            # Non-voice chain was interrupted in any case.
            self.consecutive_silent_blocks = 0
            
            # If current fragment grows too large, commit it.
            if len(self.current_voice_blocks) >= MAX_PENDING_VOICE_BLOCKS:
                # intentionally appending a list of blocks as a whole and not extending
                self.completed_fragments.append(list(self.current_voice_blocks))
                self.reset_silero(True)
                self.current_voice_blocks.clear()

            # End of voice detected blocks.
        else:
            # Silent block.
            # Should be safe to attempt resetting silero, if needed
            self.reset_silero()
            # Worth collecting to the skip buffer
            # only if we are not yet building a fragment - 
            # then it will become a prefix.
            # But no use if we are already accumulating in the voice_blocks
            if len(self.current_voice_blocks) == 0:
                self.prefix_blocks.append(block)
                # print(f"Added a prefix silence block {len(self.prefix_blocks)}")
            else:
                # We need to add it to the main deque because we are collecting all blocks now
                self.current_voice_blocks.append(block)
                # print(f"Added a voice silence block {len(self.current_voice_blocks)}")

            # count for silence commit condition
            self.consecutive_silent_blocks += 1

            # If silence persisted long enough, commit the fragment, if we have anything at all.
            # When committing, keep only up to PRE_TAIL_BLOCKS of trailing silence
            # to avoid hallucinations.
            if self.consecutive_silent_blocks >= MIN_SILENCE_WAIT_BLOCKS and len(self.current_voice_blocks) > 0:
                
                # build the fragment from the accumulated list
                # but with redundant blocks removed
                # not efficient to copy, but deque doesn't work with indexes
                cplist = list(self.current_voice_blocks)
                frag = cplist[:-REMOVE_FROM_TAIL]
                # print(f"Removing {REMOVE_FROM_TAIL}, have {len(frag)}") 

                self.completed_fragments.append(frag) # intentionally appending a list, not extending
                
                # to make sure not to lose the removed blocks
                # (which might contain quiet consonants of the next speech segment),
                # move them to the next prefix accumulator
                leftover_ix = len(cplist) - REMOVE_FROM_TAIL
                self.prefix_blocks.extend(cplist[leftover_ix:])

                self.current_voice_blocks.clear()
                self.consecutive_silent_blocks = 0
                self.reset_silero(True)

        return voice_detected


    def get_pending_voice_fragment(self):
        if not self.completed_fragments:
            return None
        frag_blocks = self.completed_fragments.popleft()
        return np.concatenate(frag_blocks)



