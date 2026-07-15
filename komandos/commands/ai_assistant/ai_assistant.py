import threading
from commands.base_command import BaseCommand
from commands.ai_assistant.avatar_display import AvatarDisplay
from ai.gemini_backend import GeminiBackend
from ai.tools.file_search_engine import engine
from PySide6 import QtCore


class AiAssistant(BaseCommand):

    def __init__(self, settings, translator, command_dispatcher):
        super().__init__(settings, translator, command_dispatcher)
        self.name = "ai_assistant"
        self.needs_context = True
        self.leaves_context_automatic = False
        self.assistant = GeminiBackend(settings, translator)
        self.lock = threading.Lock()
        # the overlay is created on the main app thread in boot()
        self.overlay = None
        self.digesting = False
        # singleton engine
        self.file_search_engine = engine


    def activate(self, _, text):
        if self.digesting:
            return
        if self.overlay:   
            # safe cross-thread calling
            QtCore.QMetaObject.invokeMethod(self.overlay, "enter", QtCore.Qt.QueuedConnection)
        self.assist(text, True)


    def in_context(self, _, text):
        if self.digesting:
            return
        if self.overlay:
            # safe cross-thread calling
            QtCore.QMetaObject.invokeMethod(self.overlay, "work", QtCore.Qt.QueuedConnection)
        self.assist(text)


    def assist(self, text, fresh_session=False):     
        t = threading.Thread(target=self.worker, daemon=True, args=[text, fresh_session])
        t.start()        


    def worker(self, text, fresh_session):
        self.digesting = True
        # prevent parallel calls
        with self.lock:
            # the manual tool handling
            # response = self.assistant.respond(text)

            # Google's SDK automatic tool handling
            response = self.assistant.process(text)
            # response = "Labdien. Nu ko jūs atkal no manis gribat?"
            print(f"AI replied: {response}")
            tts = self.command_dispatcher.get_tts_system()
            tts.generate(response)
            if fresh_session:               
                # safe cross-thread calling
                QtCore.QMetaObject.invokeMethod(self.overlay, "ready", QtCore.Qt.QueuedConnection)
            self.digesting = False


    def exit_context(self, _):
        if self.overlay:
            # safe cross-thread calling
            QtCore.QMetaObject.invokeMethod(self.overlay, "leave", QtCore.Qt.QueuedConnection)


    def boot(self):
        # boot is called the main app thread,
        # but the app is not yet inited at that point
        self.overlay = AvatarDisplay()
        print("boot ai assistant")
        # Try to load existing index, otherwise create a new one
        # On the main thread, not good...
        if not self.file_search_engine.load_index():
            self.file_search_engine.scan_and_index()
            
        # DEBUG
        # QtCore.QTimer.singleShot(100, self.debug_command_ui)


    def debug_command_ui(self):
        self.activate(None, "Oskar?")   


    def shut_down(self):
        if self.overlay:
            self.overlay.close()
            self.overlay.deleteLater()
        self.overlay = None            