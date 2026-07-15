from PySide6 import QtWidgets, QtCore, QtGui

OPACITY = 0.7

class NavOverlay(QtWidgets.QWidget):

    def __init__(self, parent=None, grid_size=3):
        super().__init__(parent)
        self.grid_size = grid_size
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.Tool)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self.setWindowFlag(QtCore.Qt.WindowTransparentForInput)
        self.setWindowOpacity(OPACITY)
        screen = QtWidgets.QApplication.primaryScreen().geometry()
        self.setGeometry(screen)

        # store OCR results as a list of bounding boxes
        # each item expected to be a tuple/list: (bbox, text, confidence)
        # where bbox is an array-like of four points or [[x1,y1],[x2,y2],...]
        self.ocr_results = []


    def paintEvent(self, _):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        pen = QtGui.QPen(QtGui.QColor(255, 0, 0), 1)
        painter.setPen(pen)
        # assume OCR results are from easyocr: list of (bbox, text, confidence)
        # where bbox is a list of four points [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
        for item in self.ocr_results:
            # expect a tuple/list with bbox as first element
            try:
                bbox = item[0]
                pts = [QtCore.QPointF(float(p[0]), float(p[1])) for p in bbox]
            except Exception:
                # ignore malformed entries; painting must not raise
                continue

            if len(pts) == 4:
                painter.drawPolygon(QtGui.QPolygonF(pts))
            elif len(pts) >= 2:
                painter.drawPolyline(QtGui.QPolygonF(pts))


    def ensure_above_taskbar(self):
        QtCore.QTimer.singleShot(10, self.raise_)


    @QtCore.Slot('QVariant')
    def set_ocr_results(self, results):
        """Thread-safe slot to receive OCR results from other threads.

        `results` is expected to be a list of items returned by easyocr.Reader.readtext
        which are typically (bbox, text, confidence).
        """
        if results is None:
            self.ocr_results = []
        else:
            self.ocr_results = [r for r in results]

        # trigger repaint
        self.update()
