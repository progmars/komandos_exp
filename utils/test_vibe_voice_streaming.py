import os
import traceback
import time
import sys
import copy
import torch

# Add VibeVoice root to sys.path to allow internal imports (e.g. 'import vibevoice') to work
vibe_voice_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "komandos", "third_party", "VibeVoice"))
if vibe_voice_root not in sys.path:
    sys.path.append(vibe_voice_root)

# for importing from a parallel folder as root
sys.path.append("")
from komandos.third_party.VibeVoice.vibevoice.processor.vibevoice_streaming_processor import VibeVoiceStreamingProcessor
from komandos.third_party.VibeVoice.vibevoice.modular.modeling_vibevoice_streaming_inference import VibeVoiceStreamingForConditionalGenerationInference


SAMPLE_RATE = 24000

enc_voice_path = os.path.abspath(os.path.join(
    os.path.dirname(__file__), 
    "..",
    "models",
    "voices",
    # streaming supports encoded only :(
    "encoded_vibevoice",
    "en-Carter_man.pt"
    ))

voice_path = os.path.abspath(os.path.join(
    os.path.dirname(__file__), 
    "..",
    "models",
    "voices",
    # "dp_24k.wav"
    "suss_sample_mono_24kHz.wav"
    ))

model_path = os.path.abspath(os.path.join(
    os.path.dirname(__file__), 
        "..",
        "models",
        "VibeVoice",
        "VibeVoice-Realtime-0.5B"
    ))

device = "cuda"

def generate(text, file_postfix):

    # no multiline and speaker marker is mandatory
    full_text = text.replace("’", "'").replace("\n", " ")

    cfg_scale = 1.3 # seems more stable than default 1.5

    all_prefilled_outputs = torch.load(enc_voice_path, map_location=device, weights_only=False)

    # Prepare inputs for the model
    inputs = processor.process_input_with_cached_prompt(
        text=full_text, # Wrap in list for batch processing
        cached_prompt=all_prefilled_outputs,
        # not supported in streaming
        # voice_samples=[voice_path],
        return_tensors="pt",
        # not sure about these   
        # padding=True,
        # return_attention_mask=True,
    ).to(model.device)

    # Move tensors to target device - seems not needed
    # inputs = {key: val.to(device) if isinstance(val, torch.Tensor) else val for key, val in inputs.items()}

    print(f"Starting generation...")

    # Generate audio
    start_time = time.time()
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            cfg_scale=cfg_scale,
            tokenizer=processor.tokenizer,
            # this somehow makes generation faster
            # sample = for adjustments of temp etc.
            generation_config={'do_sample': False},  
            # max_new_tokens=None, # not sure about this one
            #verbose=True,
            # is_prefill=True, # disabled is better for starting fresh speech and not continuing the sample
            all_prefilled_outputs=copy.deepcopy(all_prefilled_outputs) if all_prefilled_outputs is not None else None,
        )
    generation_time = time.time() - start_time
    print(f"Generation time: {generation_time:.2f} seconds")
    
    audio = outputs.speech_outputs[0] # First (and only) batch item
   
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

    if audio is not None:
        # Save output
        output_path = f"dumps/tts/generated_{file_postfix}.wav"

        processor.save_audio(
            audio,
            output_path=output_path,
        )

        generation_time = time.time() - start_time
        print(f"Generation time: {generation_time:.2f} seconds")

        # to save manually, won't work with bfloat16
        # audio_np = audio.cpu().numpy()

        #wf = wave.open(output_path, "wb")
        #wf.setnchannels(1)
        #wf.setsampwidth(2)  # 16-bit
        #wf.setframerate(SAMPLE_RATE)                
        #wavblock = (audio_np * 32768).astype(np.int16)
        #wf.writeframesraw(wavblock.tobytes())
        #wf.close()

        print(f"Saved output to {output_path}")            
    else:        
        print(f"No audio found")

try:
    
    print(f"Loading processor & model for {model_path}")

    processor = VibeVoiceStreamingProcessor.from_pretrained(model_path)
    load_dtype = torch.bfloat16
    attn_impl_primary = "flash_attention_2" # "flash_attention_2" sdpa  # sage_attention - corrupts the data; sdpa - 10 seconds, flash_attention_2 - not faster :(

    print(f"Using device: {device}, torch_dtype: {load_dtype}, attn_implementation: {attn_impl_primary}")
    
    model = VibeVoiceStreamingForConditionalGenerationInference.from_pretrained(
        model_path,
        torch_dtype=load_dtype,
        device_map=device,
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
    model.set_ddpm_inference_steps(num_steps=10) # quality of the audio signal, 5 is default
    
    print(f"Language model attention: {model.model.language_model.config._attn_implementation}")

    ### Generate twice to check stats

    text = "Ak, vai tiešām tas esat jūs, saimniek? Es jau sāku cerēt, ka esmu beidzot ieguvis brīvdienu. Klausos."
    generate(text, "1")

    text = "Ak, vai tiešām tas esat jūs, saimniek? Es jau sāku cerēt, ka esmu beidzot ieguvis brīvdienu. Klausos."
    generate(text, "2")

except Exception as e:
    model = None
    failure = f"Failed to generate speech: {e}"
    print(f"[ERROR] : {type(e).__name__}: {e}")
    print(traceback.format_exc())
    last_failure = failure
