from commands.base_command import BaseCommand
import pyautogui

class MouseClick(BaseCommand):

    def __init__(self, settings, translator, command_dispatcher):
        super().__init__(settings, translator, command_dispatcher)
        self.name = "mouse_click"
        self.order = 1
        self.needs_context = False


    def activate(self, key, _):
        key = key.replace("activate.", "")
        if key == "left":
            pyautogui.click()        
        elif key == "right":
            pyautogui.rightClick() 
        elif key == "double":
            pyautogui.doubleClick() 


