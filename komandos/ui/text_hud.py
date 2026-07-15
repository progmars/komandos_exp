from PySide6 import QtWidgets, QtCore

DISPLAY_MS = 5000
FADE_MS = 800
NORMAL_OPACITY = 0.8

class TextHud(QtWidgets.QWidget):

    def __init__(self, parent=None):
        # Use Qt.Tool so it doesn't create a taskbar icon; parent None to be top-level
        super().__init__(parent, QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)

        # Make the HUD click-through so it doesn't block mouse interaction
        # Qt 6.5+ provides WindowTransparentForInput flag
        self.setWindowFlag(QtCore.Qt.WindowTransparentForInput)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)

        # Single QLabel that will render both main text and parsed_result inline
        self.text_label = QtWidgets.QLabel("", self)

        # enable word wrap so the HUD doesn't grow wider than the screen
        self.text_label.setWordWrap(True)
        # allow rich text so we can use <span> for inline coloring
        self.text_label.setTextFormat(QtCore.Qt.RichText)
        # left-align text so the label doesn't appear centered when narrow
        self.text_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        # allow label to size to its content horizontally but expand up to
        # the available width when needed (so short text stays narrow)
        self.text_label.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Minimum)
        # add small bottom padding to push the text up a bit
        self.text_label.setStyleSheet("QLabel { background: black; padding: 0 2px 5px 2px; }")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.text_label)
        layout.addStretch() # to keep the label always at the top
        # and not stretch the box vertically when not needed
        self.layout = layout

        self.opacity_effect = QtWidgets.QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(NORMAL_OPACITY)

        self.display_timer = QtCore.QTimer(self)
        self.display_timer.setSingleShot(True)
        self.display_timer.timeout.connect(self.start_fade)

        self.fade_anim = QtCore.QPropertyAnimation(self.opacity_effect, b"opacity", self)
        self.fade_anim.setDuration(FADE_MS)
        self.fade_anim.setStartValue(NORMAL_OPACITY)
        self.fade_anim.setEndValue(0.0)
        self.fade_anim.finished.connect(self.hide)

        screen = QtWidgets.QApplication.primaryScreen()
        rect = screen.availableGeometry()
        # position at top-left of available screen area
        self.move(rect.x(), rect.y())

        # make the widget span the available width so the label can expand to
        # the full screen width when needed
        total_width = max(50, rect.width())
        # store available width for later use when showing text.
        self.max_width = total_width        
        self.setFixedWidth(total_width)



    def show_text(self, text, parsed_result=None, stick=False):
        # Build inline HTML so both pieces flow and wrap together like <span>
        def _esc(s):
            return ("" if s is None else str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))

        main_html = f"<span style='color: white; font-size:28px; font-weight:700;'>{_esc(text)}</span>"
        if parsed_result is not None:
            parsed_html = f" <span style='color: #7CFC00; font-size:28px; font-weight:700;'>-&gt; {_esc(parsed_result)}</span>"
        else:
            parsed_html = ""
        self.text_label.setText(f"{main_html} {parsed_html}")

        # Stop any ongoing fade and reset opacity
        if self.fade_anim.state() == QtCore.QAbstractAnimation.Running:
            self.fade_anim.stop()

        self.opacity_effect.setOpacity(NORMAL_OPACITY)

        # Always reset width constraints so label can shrink back
        UNCONSTRAINED = 16777215
        self.text_label.setFixedWidth(0)
        # Remove maximum constraint while measuring
        self.text_label.setMaximumWidth(UNCONSTRAINED)

        # fix vertical sizing: choose a width that fits the text
        # without unnecessarily stretching. If the text's natural width
        # (without wrapping) fits within available width, use that. If
        # it's larger, allow the label to take the full available width
        # so word-wrapping happens.
        margins = self.layout.contentsMargins()
        available_w = max(10, self.max_width - margins.left() - margins.right())

        # To measure the single-line preferred width, temporarily disable
        # word-wrap so sizeHint reports the single-line width. Then
        # restore wrapping and choose a width accordingly.
        self.text_label.setWordWrap(False)
        self.text_label.adjustSize()
        preferred_w = self.text_label.sizeHint().width()

        # Restore wrapping
        self.text_label.setWordWrap(True)

        # Choose the final width: prefer single-line preferred width when it fits
        if preferred_w <= available_w:
            self.text_label.setFixedWidth(preferred_w)
            self.text_label.setMaximumWidth(preferred_w)
        else:
            self.text_label.setFixedWidth(available_w)
            self.text_label.setMaximumWidth(available_w)

        # Update heights based on the label's sizeHint
        self.text_label.adjustSize()
        label_h = self.text_label.sizeHint().height()
        total_h = label_h + margins.top() + margins.bottom()
        self.setFixedHeight(total_h)

        self.display_timer.stop()
        if not stick:
            self.display_timer.start(DISPLAY_MS)

        self.show()


    def start_fade(self):
        # start fade animation
        self.fade_anim.stop()
        self.fade_anim.setStartValue(self.opacity_effect.opacity())
        self.fade_anim.setEndValue(0.0)
        self.fade_anim.start()
        self.opacity_effect.setOpacity(NORMAL_OPACITY)
