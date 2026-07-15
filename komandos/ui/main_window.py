from enum import Enum
from PySide6 import QtWidgets, QtCore
from i18n import translator, t
from ui.settings import Settings
from ui.image_player import ImagePlayer
from ui.text_hud import TextHud
from commands.command_dispatcher import SubEvent

class Status(Enum):
    INIT = 1
    READY = 2
    ERROR = 3
    SLEEPING = 4

STATUS_COLORS = ["#9AAFA3", "#2ECC71", "#E74C3C", "#9AAFA3"] 

class MainWindow(QtWidgets.QWidget):
    """
    A floating, frameless sidebar implemented with PySide6.
    Contains a settings button, a status indicator and a close button.
    """
    def __init__(self, settings, audio_input):
        # Use Qt.Tool so the window does not create a taskbar entry on Windows
        super().__init__(None, QtCore.Qt.Tool)

        self.settings = settings
        self.audio_input = audio_input

        # assigned later because of stalling the main thread
        self.asr_system = None
        self.tts_system = None

        # use the shared translator singleton and determine current language from persistent settings
        self.translator = translator

        # Frameless, always-on-top utility window (Qt.Tool avoids taskbar icon)
        flags = QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        # ensure the widget paints its styled background so the border and background are visible
        self.setAttribute(QtCore.Qt.WA_StyledBackground)
        
        # Use an object name and ID selector so the style applies only to this MainWindow instance. 
        self.setObjectName("MainWindow")
        self.setStyleSheet("#MainWindow{border:1px solid #ddd; border-radius:6px;}")
        
        self.status = Status.INIT

        self.sidebar_width = 60
        self.sidebar_height = 180

        self.settings_dialog = None
        self.mouse_press_pos = None
        self.mouse_move_pos = None

        # Drag handle (will be created in configure_widgets)
        self.drag_handle = None

        self.hud = TextHud()
        self.configure_widgets()

        # Health timer: checks readiness and failure reasons every 500ms
        self.health_timer = QtCore.QTimer(self)
        self.health_timer.setInterval(500)
        self.health_timer.timeout.connect(self.health_tick)
        self.health_timer.start()
        self.last_shown_error = None

        self.realign_sidebar()

        self.hud.show_text(t("loading"), stick=True)

        # force showing the dialog if no device selected
        self.is_audio_ready = False
        current_microphone = self.settings.get_setting("microphone", None)
        if current_microphone is None:
            self.hud.show_text(t("needs_audio_settings"), stick=True)
            self.open_settings()
        else:
            self.start_audio_in(current_microphone)


    def set_systems(self, asr_system, tts_system):
        self.asr_system = asr_system
        self.tts_system = tts_system

        
    def configure_widgets(self):
        layout = QtWidgets.QVBoxLayout()

        # Drag handle: small top area that is the only place you can click-and-drag
        # to move the sidebar. Installing an event filter lets us capture mouse
        # press/move/release specifically for this widget.
        self.drag_handle = QtWidgets.QLabel("=")
        self.drag_handle.setFixedHeight(18)
        self.drag_handle.setAlignment(QtCore.Qt.AlignCenter)
        self.drag_handle.setCursor(QtCore.Qt.SizeAllCursor)
        self.drag_handle.setStyleSheet("QLabel{color:#666; font-size:14px; padding-top:2px;}")
        self.drag_handle.setToolTip("Drag to move")
        self.drag_handle.installEventFilter(self)
        layout.addWidget(self.drag_handle, alignment=QtCore.Qt.AlignHCenter)

        # Status indicator as a button to capture clicks
        self.status_icon = QtWidgets.QPushButton("")
        self.status_icon.setFixedSize(40, 40)
        layout.addWidget(self.status_icon, alignment=QtCore.Qt.AlignHCenter)

        # spinner
        self.spin_icon = ImagePlayer("spinner.gif", self, 40, 40)
        layout.addWidget(self.spin_icon, alignment=QtCore.Qt.AlignHCenter)
        self.set_status(Status.INIT)
           
        # Settings button
        self.settings_button = QtWidgets.QPushButton("⛭")
        self.settings_button.setFixedSize(40, 40)
        self.settings_button.setStyleSheet("QPushButton{font-size:36px; border:none; padding:2px 4px 6px 4px;}" \
                                           "QPushButton:hover{background: #ddd;}")
        self.settings_button.clicked.connect(self.open_settings)
        layout.addWidget(self.settings_button, alignment=QtCore.Qt.AlignHCenter)

        # Close button
        self.close_button = QtWidgets.QPushButton("×")
        self.close_button.setFixedSize(40, 40)
        self.close_button.setStyleSheet("QPushButton{color:red; font-size:40px; border:none; padding:0 4px 8px 4px;}" \
                                       "QPushButton:hover{background:red; color:white;}")
        self.close_button.clicked.connect(self.close_app)
        layout.addWidget(self.close_button, alignment=QtCore.Qt.AlignHCenter)

        # without it, distributes evenly vertically
        # layout.addStretch()

        self.setLayout(layout)
        self.setFixedSize(self.sidebar_width, self.sidebar_height)


    def set_status(self, status):
        self.status = status
        if status == Status.INIT:
            self.spin_icon.show()
            self.status_icon.hide()
        else:
            self.status_icon.show()
            self.spin_icon.hide()
            color = STATUS_COLORS[self.status.value - 1]
            self.status_icon.setStyleSheet(f"background-color: {color}; border-radius: 20px;")


    def realign_sidebar(self):

        screen = QtWidgets.QApplication.primaryScreen()      
        rect = screen.availableGeometry()

        (saved_direction, saved_position) = self.settings.get_sidebar_settings()
        layout = self.layout()

        # If saved_direction is vertical, ensure vertical/top-to-bottom layout
        # Otherwise switch to a horizontal/left-to-right layout and swap sizes.
        if saved_direction == "vertical":
            if isinstance(layout, QtWidgets.QBoxLayout):
                layout.setDirection(QtWidgets.QBoxLayout.TopToBottom)
            width = self.sidebar_width
            height = self.sidebar_height
            self.setFixedSize(width, height)

            y = (rect.height() // 2) - (height // 2)

            if saved_position == "right":
                x = rect.x() + rect.width() - width
            else:  # Default to left
                x = rect.x()
        else:
            # Horizontal layout (left-to-right). Swap dimensions so width becomes
            # the previous height and height becomes the previous width.
            if isinstance(layout, QtWidgets.QBoxLayout):
                layout.setDirection(QtWidgets.QBoxLayout.LeftToRight)
            width = self.sidebar_height
            height = self.sidebar_width
            self.setFixedSize(width, height)

            x = (rect.width() // 2) - (width // 2)

            if saved_position == "bottom":
                y = rect.y() + rect.height() - height
            else:  # Default to top
                y = rect.y()

        self.move(x, y)


    def open_settings(self):
        # open single instance of the settings dialog
        if self.settings_dialog is None or not self.settings_dialog.isVisible():
            self.settings_dialog = Settings(self, self.settings, self.audio_input)
            self.settings_dialog.show()
        self.settings_dialog.activateWindow()


    def close_app(self):
        QtWidgets.QApplication.quit()


    # Draggable support    
    def eventFilter(self, obj, event):
        """
        Capture mouse events on the drag handle so dragging works only when the
        user interacts with that control.
        """
        # Only handle events coming from the drag handle
        if obj is self.drag_handle:
            t = event.type()
            if t == QtCore.QEvent.MouseButtonPress and event.button() == QtCore.Qt.LeftButton:
                self.mouse_press_pos = event.globalPosition().toPoint()
                self.mouse_move_pos = self.pos()
                return True

            if t == QtCore.QEvent.MouseMove:
                if self.mouse_press_pos is None:
                    return False
                delta = event.globalPosition().toPoint() - self.mouse_press_pos

                # Respect layout direction (horizontal vs vertical movement)
                layout = self.layout()
                direction = None
                if isinstance(layout, QtWidgets.QBoxLayout):
                    direction = layout.direction()

                if direction == QtWidgets.QBoxLayout.LeftToRight:
                    new_pos = QtCore.QPoint(self.mouse_move_pos.x() + delta.x(), self.mouse_move_pos.y())
                elif direction == QtWidgets.QBoxLayout.TopToBottom:
                    new_pos = QtCore.QPoint(self.mouse_move_pos.x(), self.mouse_move_pos.y() + delta.y())
                else:
                    new_pos = self.mouse_move_pos + delta

                # Clamp to screen
                screen = QtWidgets.QApplication.primaryScreen()
                rect = screen.availableGeometry()

                max_x = rect.x() + rect.width() - self.width()
                max_y = rect.y() + rect.height() - self.height()

                clamped_x = max(rect.x(), min(new_pos.x(), max_x))
                clamped_y = max(rect.y(), min(new_pos.y(), max_y))

                self.move(clamped_x, clamped_y)
                return True

            if t == QtCore.QEvent.MouseButtonRelease and event.button() == QtCore.Qt.LeftButton:
                self.mouse_press_pos = None
                self.mouse_move_pos = None
                return True

        return super().eventFilter(obj, event)


    def on_speech_recognized(self, text):
        # schedule UI update on the main thread using invokeMethod with typed args
        QtCore.QMetaObject.invokeMethod(self, "process_speech_events", QtCore.Qt.QueuedConnection,
                                        QtCore.Q_ARG(str, text or ""))


    def on_command_recognized(self, received, detected):
        # schedule UI update on the main thread using invokeMethod with typed args
        QtCore.QMetaObject.invokeMethod(self, "process_command_events", QtCore.Qt.QueuedConnection,
                                        QtCore.Q_ARG(str, received),
                                        QtCore.Q_ARG(str, detected))


    def on_komandos_wake_sleep(self, event):
        # schedule UI update on the main thread using invokeMethod with typed arg
        event_value = event.value
        QtCore.QMetaObject.invokeMethod(self, "process_komandos_events", QtCore.Qt.QueuedConnection,
                                        QtCore.Q_ARG(int, event_value))


    def wake(self):
        self.set_status(Status.READY)


    def sleep(self):
        self.set_status(Status.SLEEPING)


    def start_audio_in(self, idx):
        try:
            self.audio_input.start_recording(idx)            
            return True
        except Exception as e:
            # no parent to center on the screen and don't close the app from it
            QtWidgets.QApplication.setQuitOnLastWindowClosed(False)            
            QtWidgets.QMessageBox.critical(self, t("unable_start_recording"), f"{t('unable_start_recording_body')}: {e}")
            return False


    def health_tick(self):
        # ignore if inited later
        if self.audio_input is None or self.asr_system is None or self.tts_system is None:
            return

        # Check is_ready for each subsystem
        ai_ready = self.audio_input.is_ready()
        asr_ready = self.asr_system.is_ready()
        tts_ready = self.tts_system.is_ready()

        # Check failure reasons
        ai_fail = self.audio_input.get_last_failure_reason()
        asr_fail = self.asr_system.get_last_failure_reason()
        tts_fail = self.tts_system.get_last_failure_reason()

        # Update status if any subsystem reports failure (string/non-empty)
        any_fail = any(x for x in (ai_fail, asr_fail, tts_fail) if x)
        if any_fail:
            self.set_status(Status.ERROR)
            # if we have a yet unseen error, show it
            # this will get spammy if multiple systems have errors...
            error = ""
            if ai_fail and self.last_shown_error != ai_fail:
                error = ai_fail
            if asr_fail and self.last_shown_error != asr_fail:
                error = asr_fail
            if tts_fail and self.last_shown_error != tts_fail:
                error = tts_fail
            self.last_shown_error = error

            # no parent to center on the screen and don't close the app from it
            QtWidgets.QApplication.setQuitOnLastWindowClosed(False)
            QtWidgets.QMessageBox.critical(None, t("unable_start_detection"), f"{t('unable_start_detection_body')}: {error}")
        else:
            # If we were initializing, move to SLEEPING only when all ready
            if self.status == Status.INIT:
                if ai_ready and asr_ready and tts_ready:
                    self.set_status(Status.SLEEPING)
                    self.hud.show_text(t("help_hint"), stick=True)


    @QtCore.Slot(str, str)
    def process_command_events(self, received, detected):
        if detected:
            self.hud.show_text(received, detected)


    @QtCore.Slot(int)
    def process_komandos_events(self, event_value):
        event = SubEvent(event_value)
        if event == SubEvent.WAKE:
            self.wake()
        elif event == SubEvent.SLEEP:
            self.sleep()


    @QtCore.Slot(str)
    def process_speech_events(self, text):
        if text:
            self.hud.show_text(text)

