from PySide6 import QtWidgets, QtCore, QtGui
import os

class ImagePlayer(QtWidgets.QLabel):
    def __init__(self, filename, parent, width, height):
        super().__init__(parent)
        
        p = os.path.abspath(os.path.join(os.path.dirname(__file__), "assets", filename))
        self.movie = QtGui.QMovie(p)
        self.movie.setCacheMode(QtGui.QMovie.CacheAll)
        self.movie.setSpeed(100)
        self.setMovie(self.movie)
        self.setFixedSize(width, height)
        self.movie.setScaledSize(QtCore.QSize(width, height))
        self.movie.start()

