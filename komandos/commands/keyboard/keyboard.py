from commands.base_command import BaseCommand
import pyautogui
import platform

class Keyboard(BaseCommand):

    def __init__(self, settings, translator, command_dispatcher):
        super().__init__(settings, translator, command_dispatcher)
        self.name = "keyboard"
        self.order = 4
        self.needs_context = False


    def activate(self, key, _):
        key = key.replace("activate.", "")
        if platform.system() == "Darwin":
            ctrl = "command"
        else:
            ctrl = "ctrl"

        # Map i18n key to pyautogui key presses
        if key == "enter":
            pyautogui.press("enter")
        elif key == "left":
            pyautogui.press("left")
        elif key == "right":
            pyautogui.press("right")
        elif key == "up":
            pyautogui.press("up")
        elif key == "down":
            pyautogui.press("down")
        elif key == "page_up":
            pyautogui.press("pageup")
        elif key == "page_down":
            pyautogui.press("pagedown")
        elif key == "backspace":
            pyautogui.press("backspace")
        elif key == "escape":
            pyautogui.press("esc")
        elif key == "delete":
            pyautogui.press("delete")
        elif key == "tab":
            pyautogui.press("tab")
        elif key == "win":
            pyautogui.press("win")
        elif key == "select_all":
            pyautogui.hotkey(ctrl, "a")
        elif key == "copy":
            pyautogui.hotkey(ctrl, "c")
        elif key == "paste":
            pyautogui.hotkey(ctrl, "v")
        elif key == "undo":
            pyautogui.hotkey(ctrl, "z")
        elif key == "redo":
            pyautogui.hotkey(ctrl, "y")
