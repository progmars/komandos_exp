from PySide6 import QtWidgets, QtCore, QtGui

OPACITY = 0.9
AVATAR_SIZE = 256
FADE_TIME_MS = 1000

class AvatarDisplay(QtWidgets.QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.Tool)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self.setWindowFlag(QtCore.Qt.WindowTransparentForInput)

        # load images from avatars/img relative to this file
        base = QtCore.QFileInfo(__file__).absolutePath()
        img_dir = QtCore.QDir(base + "/avatars/img")

        self.pixmaps = {}
        for name in ("away", "work", "ready"):
            path = img_dir.filePath(f"{name}.png")
            if QtCore.QFile.exists(path):
                pm = QtGui.QPixmap(path)
                pm = pm.scaled(AVATAR_SIZE, AVATAR_SIZE, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
                # apply rounded corners to crop
                pm = self.round_corners(pm, radius=9)
            else:                
                pm = QtGui.QPixmap()
            self.pixmaps[name] = pm

        # create a rounded background frame
        self.frame = QtWidgets.QFrame(self)
        self.frame.setObjectName("avatar_frame")
        self.frame.setStyleSheet(
            "#avatar_frame { background-color: white; border: 1px solid #aaaaaa; border-radius: 10px; }"
        )

        # label to show avatar (inside the frame)
        self.label = QtWidgets.QLabel(self.frame)
        self.label.setScaledContents(True)

        layout = QtWidgets.QVBoxLayout(self.frame)
        layout.setContentsMargins(0, 0, 0, 0) 
        layout.setSpacing(0)
        layout.addWidget(self.label)

        size = AVATAR_SIZE + 2 # for borders
        self.setFixedSize(size, size)

        # animation for fading
        self.anim = QtCore.QPropertyAnimation(self, b"windowOpacity", self)
        self.anim.setDuration(FADE_TIME_MS)
        # whether the widget should be hidden when the animation finishes
        self.hide_after_fade = False
        self.anim.finished.connect(self.on_anim_finished)

        self.setWindowOpacity(0.0)
        self.set_pixmap("away")

        # default position: top-left of the primary screen, with small offset
        screen = QtWidgets.QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.x() + 60
            y = geo.y() + 80
            self.move(x, y)


    def round_corners(self, pixmap: QtGui.QPixmap, radius: int) -> QtGui.QPixmap:
        """
        Returns a new QPixmap with rounded corners and transparent background.
        """
        # Create a transparent pixmap of the same size
        rounded = QtGui.QPixmap(pixmap.size())
        rounded.fill(QtCore.Qt.GlobalColor.transparent)

        # Paint the original image onto the transparent one using a clipping path
        painter = QtGui.QPainter(rounded)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        
        # Create the rounded path
        path = QtGui.QPainterPath()
        path.addRoundedRect(QtCore.QRectF(pixmap.rect()), radius, radius)
        
        # Clip and Draw
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, pixmap)
        painter.end()
        
        return rounded


    def set_pixmap(self, name):
        pm = self.pixmaps.get(name)
        if pm and not pm.isNull():
            self.label.setPixmap(pm)
        else:
            self.label.clear()


    @QtCore.Slot()
    def leave(self):
        self.set_pixmap("away")
        self.anim.stop()
        # request hide when the animation completes
        self.hide_after_fade = True
        self.anim.setStartValue(self.windowOpacity())
        self.anim.setEndValue(0.0)
        self.anim.setDuration(250)
        self.anim.start()


    @QtCore.Slot()
    def enter(self):
        self.set_pixmap("away")
        self.anim.stop()
        # ensure we don't hide when this animation finishes
        self.hide_after_fade = False
        self.anim.setStartValue(self.windowOpacity())
        self.anim.setEndValue(OPACITY)
        self.anim.setDuration(250)
        self.show()
        self.anim.start()


    @QtCore.Slot()
    def work(self):
        self.set_pixmap("work")


    @QtCore.Slot()
    def ready(self):
        self.set_pixmap("ready")


    def on_anim_finished(self):
        # single central handler for finished signal. Hide only when
        # a fade-out requested it (avoid repeated connects/disconnects).
        if self.hide_after_fade and self.windowOpacity() == 0.0:
            self.hide()
        # reset the flag so future finishes won't unexpectedly hide
        self.hide_after_fade = False
