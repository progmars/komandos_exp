import argparse
import sys

# Prevent PyAutoGUI and pywinctl from setting Process DPI Awareness, which Qt tries to do then throws warnings about it.
# https://github.com/asweigart/pyautogui/issues/663#issuecomment-1296719464
# QT doesn't call those from Python/ctypes, meaning we can stop other programs from setting it.
if sys.platform == "win32":
    from ctypes import windll
    # pyautogui._pyautogui_win.py
    windll.user32.SetProcessDPIAware = lambda: None  # pyright: ignore[reportAttributeAccessIssue]
    # pymonctl._pymonctl_win.py
    # pywinbox._pywinbox_win.py
    windll.shcore.SetProcessDpiAwareness = (  # pyright: ignore[reportAttributeAccessIssue]
        lambda _: None  # pyright: ignore[reportUnknownLambdaType]
    )

import pyautogui
from settings import Settings
from audio.input import Input
from audio.output import Output
from asr.asr import AutomaticSpeechRecognizer
from app import App
from i18n import translator
from commands.command_dispatcher import CommandDispatcher


def parse_args():
    parser = argparse.ArgumentParser(description="Launch Komandos with environment setting")
    parser.add_argument(
        "-e",
        "--env",
        choices=["dev", "prod"],
        default="prod",
        help="Environment to use (dev or prod). If 'dev' the settings.dev.yaml will be used.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(f"Env: {args.env}")

    # from ai.tools.tool_dispatcher import find_file_path_by_parts    
    # from ai.tools.file_search_engine import engine

    # file_search_engine = engine
    # if not file_search_engine.load_index():
    #     file_search_engine.scan_and_index()

    # find_file_path_by_parts("dusmīgs putns")
    # find_file_path_by_parts("liviju")
    # exit(0)

    # wire all components together
    settings = Settings(args.env)
    lang = settings.get_setting("language", "en")
    translator.set_language(lang)

    saved_boost = int(settings.get_setting("microphone_boost", 0))
    audio_input = Input(saved_boost, args.env == "dev",
                        add_input_wav_simulator_device = args.env == "dev") # , "dumps/debug_in.wav")
    audio_output = Output() # future: saved output device init

    command_dispatcher = CommandDispatcher(settings, translator)    
    # create app first, as some bootables need UI
    # and Qt app must be registered to be able to create widgets
    main_app = App(settings, audio_input, command_dispatcher, sys.argv)

    # we want to already show the app UI once, even if it's frozen for a while
    # just to make it known to the user that the app is doing something
    main_app.show()

    # vibe_voice import stalls the thread and cannot be moved to loading later 
    # because then torch complains about
    # "UserWarning: for conv_cls.0.weight: copying from a non-meta parameter in the checkpoint to a meta parameter in the current model, which is a no-op." 
    # and "Failed to instantiate module: Cannot copy out of meta tensor; no data! "
    from tts.vibe_voice import VibeVoice   
    tts_system = VibeVoice(output_handler=audio_output.play)
    asr_system = AutomaticSpeechRecognizer(lang, command_dispatcher.get_asr_word_guide(),
                                           args.env == "dev")
    
    main_app.set_systems(asr_system, tts_system)
    command_dispatcher.set_systems(asr_system, tts_system)

    asr_system.subscribe(main_app.on_speech_recognized)
    audio_input.subscribe(asr_system.on_audio_arrived)
    asr_system.subscribe(command_dispatcher.on_text_arrived)

    rc = None

    try:
        # this will be superheavy because of VibeVoice - 
        # the only TTS that can kinda speak Latvian with emotions
        tts_system.boot()
        asr_system.boot()

        # this also catches for a second because of scanning
        # and building command UIs on the main thread
        command_dispatcher.boot()
        rc = main_app.run()
    except Exception as e:
        pyautogui.alert(f"Fatal error while running the app: {e}", "Error")
        raise e
    finally:
        try:
            command_dispatcher.shut_down()
            audio_input.shut_down()
            asr_system.shut_down()
            tts_system.shut_down()
        except Exception as e:
            print(f"Shutdown problem: {e}")
            pass

    sys.exit(rc)