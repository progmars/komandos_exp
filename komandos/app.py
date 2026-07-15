from PySide6 import QtWidgets
from ui.main_window import MainWindow
from commands.command_dispatcher import Event

class App:
    """
    Lightweight application container for Qt.
    """
    def __init__(self, settings, audio_input, command_dispatcher, sysargs):
        self.qapp = QtWidgets.QApplication(sysargs)

        QtWidgets.QApplication.setStyle("Fusion") 
        # widgets support Fusion, Windows, WindowsVista, Macintosh styles,
        # depending on OS. Fusion is OK, uses OS accents on Windows 10+

        # set a larger font size across the entire application (keeps previous behavior)
        self.qapp.setStyleSheet("QWidget{font-size: 14px;}")

        # Create and show the floating MainWindow
        self.main_window = MainWindow(settings, audio_input)
        self.main_window.show()

        self.command_dispatcher = command_dispatcher

        # and subscribe to display detected commands
        self.command_dispatcher.subscribe(Event.COMMAND_DETECTED, self.main_window.on_command_recognized)
        self.command_dispatcher.subscribe(Event.WAKE_SLEEP, self.main_window.on_komandos_wake_sleep)

        # when the App is created, now init dispatcher UI parts
        # that need main thread
        self.command_dispatcher.initialize_ui_dependencies()


    def show(self):
        self.qapp.processEvents()


    def set_systems(self, asr_system, tts_system):
        self.main_window.set_systems(asr_system, tts_system)


    def on_speech_recognized(self, text):
        self.main_window.on_speech_recognized(text)


    def run(self):
        # Run the Qt event loop. Use the QApplication instance stored on mainApp if available.
        return self.qapp.exec()