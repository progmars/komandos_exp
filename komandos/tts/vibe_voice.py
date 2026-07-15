import threading
import os
import sys
import traceback
import time
import torch

# Add VibeVoice root to sys.path to allow internal imports (e.g. 'import vibevoice') to work
vibe_voice_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "komandos", "third_party", "VibeVoice"))
if vibe_voice_root not in sys.path:
    sys.path.append(vibe_voice_root)

from third_party.VibeVoice.vibevoice.processor.vibevoice_processor import VibeVoiceProcessor
from third_party.VibeVoice.vibevoice.modular.modeling_vibevoice_inference import VibeVoiceForConditionalGenerationInference

SAMPLE_RATE = 24000

# logging.set_verbosity_info()
# logger = logging.get_logger(__name__)

class VibeVoice:
    def __init__(self, output_handler):
        self.output_handler = output_handler
        self.voice_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), 
            "..",
            "..",
            "models",
            "voices",
            # "dp_24k.wav"
            "suss_sample_mono_24kHz.wav"
            ))

        self.model_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), 
            "..",
            "..",
            "models",
            "VibeVoice",

            # "VibeVoice-7B",
            # or
            # "VibeVoice-Large-Q8"

            # or
            "VibeVoice7b-low-vram",
            "4bit"
            ))
        self.last_failure = None   
        self.device = "cuda"
        # The heavy model/processor will be loaded on a background thread.
        self.processor = None
        self.model = None
        self.lock = threading.Lock()
        

    def boot(self):
        # Start model loading in a background thread to avoid blocking UI.
        t = threading.Thread(target=self.load_models, daemon=True)
        t.start()


    def load_models(self):
        # prevent parallel calls while model loads
        with self.lock:
            print(f"Loading processor & model for {self.model_path}")

            try:
                # The heavy modules (torch and VibeVoice classes) are imported on
                # the main thread to avoid thread-related issues; now just use them.
                self.processor = VibeVoiceProcessor.from_pretrained(self.model_path)
                load_dtype = torch.bfloat16 # float16 if warnings
                attn_impl_primary = "sdpa" # "flash_attention_2" does not give any benefits for short sentences

                model = VibeVoiceForConditionalGenerationInference.from_pretrained(
                    self.model_path,
                    torch_dtype=load_dtype,
                    device_map=self.device,
                    local_files_only=True,
                    attn_implementation=attn_impl_primary,
                )

                """
                with torch.no_grad: disables computation of gradients for the backward pass. 
                Since these calculations are unnecessary during inference, and add non-trivial computational overhead, 
                it is essessential to use this context if evaluating the model's speed. It will not however affect results.
                model.eval() ensures certain modules which behave differently in training vs inference
                (e.g. Dropout and BatchNorm) are defined appropriately during the forward pass in inference.
                As such, if your model contains such modules it is essential to enable this.
                For the reasons above it is good practice to use both during inference.
                """
                model.eval()
                model.set_ddpm_inference_steps(num_steps=5) # quality of the audio signal, 5 is default

                if hasattr(model.model, 'language_model'):
                    print(f"Language model attention: {model.model.language_model.config._attn_implementation}")

                # the last step
                self.model = model


            except Exception as e:
                self.model = None
                failure = f"Failed to initialize speech synthesis: {e}"
                print(f"[ERROR] : {type(e).__name__}: {e}")
                print(traceback.format_exc())
                self.last_failure = failure
                return


    def generate(self, text):
        # prevent parallel calls while processing
        with self.lock:
            if self.model is None or text is None:
                return
            
            # no multiline and speaker marker is mandatory
            full_text = "Speaker 1:" + text.replace("’", "'").replace("\n", " ")

            cfg_scale = 1.3

            # this somehow makes generation faster
            # sample = for adjustments of temp etc.
            generation_config={'do_sample': False},

            # Prepare inputs for the model
            inputs = self.processor(
                text=full_text,
                voice_samples=[self.voice_path],
                padding=True,
                return_tensors="pt",
                return_attention_mask=True,
            ).to(self.model.device)

            # Move tensors to target device - seems not needed
            # inputs = {key: val.to(device) if isinstance(val, torch.Tensor) else val for key, val in inputs.items()}

            print(f"Starting generation with cfg_scale: {cfg_scale}")

            # Generate audio
            start_time = time.time()
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=None,
                    cfg_scale=cfg_scale,
                    tokenizer=self.processor.tokenizer,
                    generation_config=generation_config,
                    #verbose=True,
                    # is_prefill=True, # disabled is better for starting fresh speech and not continuing the sample
                )
            generation_time = time.time() - start_time
            print(f"Generation time: {generation_time:.2f} seconds")
            
            audio = outputs.speech_outputs[0] # First (and only) batch item

            """
            # Calculate audio duration and additional metrics
            if outputs.speech_outputs and outputs.speech_outputs[0] is not None:
                # Assuming 24kHz sample rate (common for speech synthesis)
                sample_rate = 24000
                audio_samples = outputs.speech_outputs[0].shape[-1] if len(outputs.speech_outputs[0].shape) > 0 else len(outputs.speech_outputs[0])
                audio_duration = audio_samples / sample_rate
                rtf = generation_time / audio_duration if audio_duration > 0 else float('inf')
                
                print(f"Generated audio duration: {audio_duration:.2f} seconds")
                print(f"RTF (Real Time Factor): {rtf:.2f}x")
            else:
                print("No audio output generated")
            
            # Calculate token metrics
            input_tokens = inputs['input_ids'].shape[1]  # Number of input tokens
            output_tokens = outputs.sequences.shape[1]  # Total tokens (input + generated)
            generated_tokens = output_tokens - input_tokens
            
            print(f"Prefilling tokens: {input_tokens}")
            print(f"Generated tokens: {generated_tokens}")
            print(f"Total tokens: {output_tokens}")
            """

            # Save output
            output_path = "dumps/tts/generated.wav"

            self.processor.save_audio(
                outputs.speech_outputs[0], # First (and only) batch item
                output_path=output_path,
            )
            print(f"Saved output to {output_path}")            

            # Convert PyTorch tensor to numpy
            audio_np = audio.float().detach().cpu().numpy().flatten()

            self.output_handler(audio_np, SAMPLE_RATE)
            

    def is_ready(self):
        return self.model is not None


    def get_last_failure_reason(self):
        return self.last_failure


    def shut_down(self):
        self.model = None
          


        