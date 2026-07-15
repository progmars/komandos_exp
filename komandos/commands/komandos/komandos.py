import pyautogui
from PySide6 import QtCore
from commands.base_command import BaseCommand
from commands.komandos.help_popup import HelpPopup

"""
Commands for controlling KomandOS itself
"""
class Komandos(BaseCommand):

    def __init__(self, settings, translator, command_dispatcher):        
        super().__init__(settings, translator, command_dispatcher)
        self.command_dispatcher = command_dispatcher
        self.order = 0
        # the only known special case that can be active during sleep
        self.override_sleep = True
        self.overlay = None
        self.name = "komandos"
        self.needs_context = True # because of popup
        # we'll set it to False dynamically when needed
        self.leaves_context_automatic = True


    def activate(self, key, _):
        key = key.replace("activate.", "")
        if key == "wake":
            self.command_dispatcher.wake()       
        elif key == "sleep":
            self.command_dispatcher.sleep() 
        elif key == "help":
            self.open_help()


    # minumum commands to scroll the help view
    def in_context(self, key, word):
        if key == "in_context.up":
            pyautogui.press("up")
        elif key == "in_context.down":
            pyautogui.press("down")
        elif key == "in_context.page_up":
            pyautogui.press("pageup")
        elif key == "in_context.page_down":
            pyautogui.press("pagedown")


    def exit_context(self, word): 
        self.leaves_context_automatic = True
        if self.overlay:
            # safe cross-thread calling
            QtCore.QMetaObject.invokeMethod(self.overlay, "hide", QtCore.Qt.QueuedConnection)


    def boot(self):
        # ensure the overlay is created on the main app thread
        contents = "".join(self.command_dispatcher.get_descriptions())
        self.overlay = HelpPopup(contents)


    def shut_down(self):
        if self.overlay:
            self.overlay.close()
            self.overlay.deleteLater()
        self.overlay = None


    def open_help(self):
        # to block until close the help view
        self.leaves_context_automatic = False
        # safe cross-thread calling
        QtCore.QMetaObject.invokeMethod(self.overlay, "show", QtCore.Qt.QueuedConnection)
