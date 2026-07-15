from PySide6 import QtWidgets, QtCore
import time
import threading
from .level_bar import LevelBar
from i18n import translator, t


class Settings(QtWidgets.QDialog):
    """
    PySide6-based settings dialog with Audio, Commands and UI tabs.
    """
    # must be a class variable
    # Signal used to update the level meter from any thread (queued to the GUI thread)
    # changed to object so we can pass raw numpy blocks for RMS computation
    level_signal = QtCore.Signal(object)
    
    def __init__(self, parent, settings, audio_input):
        super().__init__(parent)

        # need to keep own ref; Qt parent does not know our Python window well
        self.owner = parent

        # use the shared translator singleton and determine current language from persistent settings
        self.translator = translator
        self.settings = settings
        self.current_language = self.settings.get_setting("language", self.translator.current_language)

        self.translator.set_language(self.current_language)

        self.audio_input = audio_input

        # level update throttling state
        self.level_lock = threading.Lock()
        self.last_level_emit = 0.0

        # connect cross-thread signal to GUI updater
        self.level_signal.connect(self.set_input_level)

        self.setWindowTitle(t("title"))
        self.resize(500, 500)

        self.center_window()

        self.tab_view = QtWidgets.QTabWidget(self)

        # create tabs using translated names
        self.audio_tab = QtWidgets.QWidget()
        self.commands_tab = QtWidgets.QWidget()
        self.ui_tab = QtWidgets.QWidget()

        self.tab_view.addTab(self.audio_tab, t("tabs.audio"))
        # self.tab_view.addTab(self.commands_tab, t("tabs.commands"))
        self.tab_view.addTab(self.ui_tab, t("tabs.ui"))

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.addWidget(self.tab_view)

        # keep references to widgets that need dynamic text updates
        self.device_index_map = {}

        self.configure_audio_tab()
        # self.configure_commands_tab()
        self.configure_ui_tab()


    def center_window(self):
        self.adjustSize()
        screen = QtWidgets.QApplication.primaryScreen()
        if screen:
            rect = screen.availableGeometry()
            x = rect.x() + (rect.width() - self.width()) // 2
            y = rect.y() + (rect.height() - self.height()) // 2
            self.move(x, y)


    def configure_audio_tab(self):
        layout = QtWidgets.QVBoxLayout(self.audio_tab)

        # instruction label: allow wrapping and justify text horizontally
        # store as instance attribute so it can be updated dynamically if needed
        self.audio_instruct = QtWidgets.QLabel(t("audio_welcome_body"), self.audio_tab)
        self.audio_instruct.setWordWrap(True)
        self.audio_instruct.setAlignment(QtCore.Qt.AlignJustify)
        self.audio_instruct.setStyleSheet("border: 1px solid #ddd; padding: 6px; border-radius: 4px;")

        layout.addWidget(self.audio_instruct)

        self.microphone_label = QtWidgets.QLabel(t("input_device"), self.audio_tab)
        layout.addWidget(self.microphone_label)

        self.process_input_device_list(layout)

        # --- Microphone boost control ---------------------------------
        # Slider to adjust boost level (stored as integer percent)
        boost_frame = QtWidgets.QFrame(self.audio_tab)
        boost_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        boost_layout = QtWidgets.QHBoxLayout(boost_frame)

        self.boost_label = QtWidgets.QLabel(t("microphone_boost"), boost_frame)
        boost_layout.addWidget(self.boost_label)

        # get saved boost (default 0)
        saved_boost = int(self.settings.get_setting("microphone_boost", 0))

        self.boost_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal, boost_frame)
        self.boost_slider.setMinimum(0)
        self.boost_slider.setMaximum(2000) # 10x more for some stubborn USB mics
        self.boost_slider.setValue(saved_boost)
        self.boost_slider.setTickInterval(10)
        self.boost_slider.setTickPosition(QtWidgets.QSlider.TicksBelow)
        boost_layout.addWidget(self.boost_slider)

        # display numeric value
        self.boost_value_label = QtWidgets.QLabel(f"{saved_boost}%", boost_frame)
        boost_layout.addWidget(self.boost_value_label)

        # wire change handler
        self.boost_slider.valueChanged.connect(self.boost_changed)

        layout.addWidget(boost_frame)

        # --- Input level meter ----------------------------------------
        self.level_label = QtWidgets.QLabel(t("input_level"), self.audio_tab)
        layout.addWidget(self.level_label)

        self.level_bar = LevelBar(self.audio_tab)
        layout.addWidget(self.level_bar)

        # Subscribe to audio input blocks so we can update the level meter.
        # The callback runs in the audio dispatch thread; it will emit a Qt signal
        # which is safely queued to the GUI thread.
        self.audio_input.subscribe(self.audio_block_received)

        # push widgets to the top of the tab; any remaining space goes below
        layout.addStretch()


    def set_input_level(self, block):
        if self.level_bar:
            self.level_bar.set_level(block)


    def audio_block_received(self, block):
        """Callback subscribed to audio input dispatcher.
        Runs in the audio dispatch thread. 
        Throttles updates to ~50ms, and emits a queued Qt signal to update GUI.
        """
        now = time.time()
        with self.level_lock:
            if now - self.last_level_emit < 0.100:
                return
            self.last_level_emit = now

        try:
            self.level_signal.emit(block.copy())
        except Exception:
            pass


    def closeEvent(self, event):
        """Ensure we unsubscribe from audio input when dialog closes."""
        try:
            if self.audio_input is not None:
                self.audio_input.unsubscribe(self.audio_block_received)
        except Exception:
            pass

        super().closeEvent(event)


    def process_input_device_list(self, layout):
        
        last_microphone = self.settings.get_setting("microphone", None)

        current_microphone = None
        self.device_index_map = {}

        try:
            input_device_names = []

            devices = self.audio_input.enumerate_devices()
            for dev in devices:
                dev_index = dev.get("index")
                dev_name = dev.get("name")
                display = dev_name
                self.device_index_map[display] = dev_index
                input_device_names.append(display)
                if last_microphone == dev_index:
                    current_microphone = dev_index

            if not input_device_names:
                not_found = QtWidgets.QLabel(t("no_input_devices"), self.audio_tab)
                layout.addWidget(not_found)
            else:
                current_microphone_name = None
                for name, i in self.device_index_map.items():
                    if i == current_microphone:
                        current_microphone_name = name
                        break

                self.device_combo = QtWidgets.QComboBox(self.audio_tab)
                self.device_combo.addItems(input_device_names)
                if current_microphone_name:
                    index = self.device_combo.findText(current_microphone_name)
                    if index >= 0:
                        self.device_combo.setCurrentIndex(index)
                self.device_combo.currentTextChanged.connect(self.audio_device_changed)
                layout.addWidget(self.device_combo)

                apply_btn = QtWidgets.QPushButton(t("apply"), self.audio_tab)
                apply_btn.clicked.connect(self.apply_audio_selection)
                layout.addWidget(apply_btn)

        except Exception as e:
            print(f"Error enumerating input devices: {e}")
            fallback = QtWidgets.QLabel(t("unable_enumerate"), self.audio_tab)
            layout.addWidget(fallback)


    def boost_changed(self, value):
        self.boost_value_label.setText(f"{int(value)}%")
        self.settings.save_setting("microphone_boost", int(value))
        self.audio_input.set_boost(int(value))


    def configure_ui_tab(self):
        layout = QtWidgets.QVBoxLayout(self.ui_tab)

        (saved_direction, saved_position) = self.settings.get_sidebar_settings()

        # --- Language frame -------------------------------------------------
        lang_frame = QtWidgets.QFrame(self.ui_tab)
        lang_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        lang_layout = QtWidgets.QVBoxLayout(lang_frame)

        # language selection
        languages = []
        lang_display_map = {}
        for code, name in self.translator.available_languages().items():
            languages.append(name)
            lang_display_map[name] = code

        selected_display = None
        for name, code in lang_display_map.items():
            if code == self.current_language:
                selected_display = name
                break

        self.language_label = QtWidgets.QLabel(t("language"), lang_frame)
        lang_layout.addWidget(self.language_label)

        self.language_combo = QtWidgets.QComboBox(lang_frame)
        self.language_combo.addItems(languages)
        if selected_display:
            idx = self.language_combo.findText(selected_display)
            if idx >= 0:
                self.language_combo.setCurrentIndex(idx)

        # map selection to language code
        self.lang_display_map = lang_display_map
        self.language_combo.currentTextChanged.connect(lambda v: self.language_changed(self.lang_display_map.get(v)))
        lang_layout.addWidget(self.language_combo)

        layout.addWidget(lang_frame)

        # --- Alignment frame ------------------------------------------------
        align_frame = QtWidgets.QFrame(self.ui_tab)
        align_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        align_layout = QtWidgets.QVBoxLayout(align_frame)

        self.alignment_label = QtWidgets.QLabel(t("sidebar_alignment"), align_frame)
        align_layout.addWidget(self.alignment_label)

        # Arrangement selector (vertical / horizontal)
        arr_group = QtWidgets.QGroupBox(t("arrangement"), align_frame)
        arr_layout = QtWidgets.QHBoxLayout(arr_group)
        self.vertical_radio = QtWidgets.QRadioButton(t("vertical"), arr_group)
        self.horizontal_radio = QtWidgets.QRadioButton(t("horizontal"), arr_group)
        if saved_direction == "vertical":
            self.vertical_radio.setChecked(True)
        else:
            self.horizontal_radio.setChecked(True)
        arr_layout.addWidget(self.vertical_radio)
        arr_layout.addWidget(self.horizontal_radio)
        align_layout.addWidget(arr_group)

        # Position selectors: vertical -> left/right, horizontal -> top/bottom
        self.vertical_group = QtWidgets.QGroupBox(t("position"), align_frame)
        v_layout = QtWidgets.QHBoxLayout(self.vertical_group)
        self.left_radio = QtWidgets.QRadioButton(t("left"), self.vertical_group)
        self.right_radio = QtWidgets.QRadioButton(t("right"), self.vertical_group)
        if saved_position in ("left", "right"):
            if saved_position == "left":
                self.left_radio.setChecked(True)
            else:
                self.right_radio.setChecked(True)
        else:
            self.left_radio.setChecked(True)
        v_layout.addWidget(self.left_radio)
        v_layout.addWidget(self.right_radio)
        align_layout.addWidget(self.vertical_group)

        self.horizontal_group = QtWidgets.QGroupBox(t("position"), align_frame)
        h_layout = QtWidgets.QHBoxLayout(self.horizontal_group)
        self.top_radio = QtWidgets.QRadioButton(t("top"), self.horizontal_group)
        self.bottom_radio = QtWidgets.QRadioButton(t("bottom"), self.horizontal_group)
        if saved_position in ("top", "bottom"):
            if saved_position == "top":
                self.top_radio.setChecked(True)
            else:
                self.bottom_radio.setChecked(True)
        else:
            self.top_radio.setChecked(True)

        h_layout.addWidget(self.top_radio)
        h_layout.addWidget(self.bottom_radio)
        align_layout.addWidget(self.horizontal_group)

        # show only the relevant position group
        self.vertical_group.setVisible(saved_direction == "vertical")
        self.horizontal_group.setVisible(saved_direction == "horizontal")

        # signal wiring (preserve behaviour)
        self.vertical_radio.toggled.connect(lambda checked: self.sidebar_direction_changed("vertical") if checked else None)
        self.horizontal_radio.toggled.connect(lambda checked: self.sidebar_direction_changed("horizontal") if checked else None)

        self.left_radio.toggled.connect(lambda checked: self.sidebar_position_changed("left") if checked else None)
        self.right_radio.toggled.connect(lambda checked: self.sidebar_position_changed("right") if checked else None)
        self.top_radio.toggled.connect(lambda checked: self.sidebar_position_changed("top") if checked else None)
        self.bottom_radio.toggled.connect(lambda checked: self.sidebar_position_changed("bottom") if checked else None)

        layout.addWidget(align_frame)

        # keep everything at the top
        layout.addStretch()


    def configure_commands_tab(self):
        layout = QtWidgets.QVBoxLayout(self.commands_tab)

        self.commands_label = QtWidgets.QLabel(t("command_settings"), self.commands_tab)
        layout.addWidget(self.commands_label)
        textbox = QtWidgets.QTextEdit(self.commands_tab)
        textbox.setFixedHeight(100)
        layout.addWidget(textbox)

        # push widgets to the top so the tab doesn't distribute them vertically
        layout.addStretch()


    def sidebar_position_changed(self, value):
        # Deprecated: kept for backwards compatibility if other code calls it.
        # Expecting a translated label; try to infer the logical side.
        if value == t("left"):
            side = "left"
        elif value == t("right"):
            side = "right"
        elif value == t("top"):
            side = "top"
        elif value == t("bottom"):
            side = "bottom"
        else:
            # fallback to provided value
            side = value

        self.settings.save_setting("position", side)
        self.owner.realign_sidebar()


    def sidebar_direction_changed(self, direction):
        """Called when the user switches between vertical/horizontal arrangement."""

        self.settings.save_setting("direction", direction)

        self.vertical_group.setVisible(direction == "vertical")
        self.horizontal_group.setVisible(direction == "horizontal")

        # ensure a sensible position is selected for the chosen direction
        current_position = self.settings.get_setting("position", "left")
        
        new_position = current_position

        if direction == "vertical":
            if current_position not in ("left", "right"):
                # default to left
                self.left_radio.setChecked(True)                
                new_position = "left"
        else:
            if current_position not in ("top", "bottom"):
                # default to top
                self.top_radio.setChecked(True)
                new_position = "top"

        if new_position != current_position:
            self.settings.save_setting("position", new_position)
            self.owner.realign_sidebar()


    def language_changed(self, code):
        if code is None:
            return
        # set and persist language
        self.current_language = code

        # update translator so the restart message is shown in the selected language
        self.translator.set_language(code)
        self.settings.save_setting("language", code)

        # Inform the user that a restart is required for language changes to apply
        QtWidgets.QMessageBox.information(self, self.translator.t("restart_required_title"), self.translator.t("restart_required_body"))


    def audio_device_changed(self, selection):
        idx = self.device_index_map.get(selection)
        # don't save until applied


    def apply_audio_selection(self):
        """Called when the user clicks Apply: persist selection and attempt to start recording."""
        try:
            selection = self.device_combo.currentText()
        except Exception:
            selection = None

        if not selection:
            QtWidgets.QMessageBox.warning(self, t("no_device_selected"), t("please_select_device"))
            return

        idx = self.device_index_map.get(selection)

        if self.owner.start_audio_in(idx):        
            self.settings.save_setting("microphone", idx)
