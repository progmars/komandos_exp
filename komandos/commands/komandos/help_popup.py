import pyautogui
from PySide6 import QtWidgets, QtCore, QtGui

class HelpPopup(QtWidgets.QWidget):

    def __init__(self, contents="", parent=None):
        super().__init__(parent)

        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.Tool)
        # enable per-pixel transparency for the window (so rounded corners can be truly transparent)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        
        # create a rounded background frame that will hold the text browser
        self.frame = QtWidgets.QFrame(self)
        self.frame.setObjectName("help_frame")
        self.frame.setStyleSheet("#help_frame { background-color: #eeeeee; border: 1px solid #aaaaaa; border-radius: 30px; }")

        self.browser = QtWidgets.QTextBrowser(self.frame)
        self.browser.setObjectName("help_browser")
        self.browser.setStyleSheet("#help_browser { background-color: transparent; }")
        self.browser.setOpenExternalLinks(True)
        self.browser.setReadOnly(True)
        self.browser.setHtml(contents)

        # layout inside frame
        layout = QtWidgets.QVBoxLayout(self.frame)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(self.browser)

        # size and position: about 80% of available geometry of primary screen
        screen = QtGui.QGuiApplication.primaryScreen()
        geom = screen.availableGeometry()

        SIZE_FAC = 0.8
        w = int(geom.width() * SIZE_FAC)
        h = int(geom.height() * SIZE_FAC)
        x = geom.x() + (geom.width() - w) // 2
        y = geom.y() + (geom.height() - h) // 2
        self.setGeometry(x, y, w, h)
        self.frame.setGeometry(0, 0, w, h)
        self.browser.setGeometry(12, 12, w - 24, h - 24)

        # self.show()
        # initially hidden

    def showEvent(self, evt):
        if evt.type() == QtCore.QEvent.Show:
            QtCore.QTimer.singleShot(50, self.center_focus)


    def center_focus(self):
        # did not work
        # self.raise_()
        # self.setFocus()
        # self.activateWindow()

        # needs some nudging to center cursor and click
        screen = QtGui.QGuiApplication.primaryScreen()
        geom = screen.availableGeometry()
        pyautogui.moveTo(geom.width()//2, geom.height()//2)
        pyautogui.click()