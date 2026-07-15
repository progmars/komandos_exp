
from commands.base_command import BaseCommand
import pyautogui
import pyperclip
import platform

class Dictate(BaseCommand):

    def __init__(self, settings, translator, command_dispatcher):
        super().__init__(settings, translator, command_dispatcher)
        self.name = "dictate"
        self.needs_context = True
        self.leaves_context_automatic = False


    def in_context(self, _, text):
        try:
            pyperclip.copy(text)
            if platform.system() == "Darwin":
                pyautogui.hotkey("command", "v")
            else:
                pyautogui.hotkey("ctrl", "v")
        except Exception as e:
            print(f"Failed to write: {e}")
            return


