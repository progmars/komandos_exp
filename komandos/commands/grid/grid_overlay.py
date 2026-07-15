from PySide6 import QtWidgets, QtCore, QtGui

OPACITY = 0.7

class GridOverlay(QtWidgets.QWidget):

    def __init__(self, parent=None, grid_size=3):
        super().__init__(parent)
        self.grid_size = grid_size
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.Tool)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self.setWindowFlag(QtCore.Qt.WindowTransparentForInput)
        self.level = 0 # 0,1,2,3,4
        self.setWindowOpacity(OPACITY)
        self.numbers = [str(i+1) for i in range(grid_size*grid_size)]
        self.resize_screen()


    def resize_screen(self):
        screen = QtWidgets.QApplication.primaryScreen().geometry()
        self.setGeometry(screen)
        self.update()
        self.ensure_above_taskbar()


    def paintEvent(self, _):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cell_w, cell_h = w // self.grid_size, h // self.grid_size
        pen = QtGui.QPen(QtGui.QColor(255, 0, 0), 1)
        painter.setPen(pen)

        # Draw grid lines or outer border depending on level
        if self.level == 4:
            # Only draw outer rectangle (border)
            rect_pen = QtGui.QPen(QtGui.QColor(255, 0, 0), 2)
            painter.setPen(rect_pen)
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawRect(0, 0, w-1, h-1)
        else:
            # Draw internal grid lines
            for i in range(self.grid_size+1):
                painter.drawLine(i*cell_w, 0, i*cell_w, h)
                painter.drawLine(0, i*cell_h, w, i*cell_h)

        # Draw numbers with black background boxes
        # Set font size and box_size based on self.level and cell size
        # Deeper level -> smaller font and box. Keep sizes proportional to cell.
        # base scale (level 0) uses a fraction of the smaller cell dimension
        min_cell = min(cell_w, cell_h)
        # scale factors per level
        level_scales = {0: 0.25, 1: 0.18, 2: 0.12}
        scale = level_scales.get(self.level, 0.12)
        box_size = max(12, int(min_cell * scale))

        # font point size proportional to box_size (rough heuristic)
        font_point = max(8, int(box_size * 0.6))
        font = QtGui.QFont("Arial", font_point)
        painter.setFont(font)

        # Do not draw numbers for level 4
        if self.level != 4:
            for y in range(self.grid_size):
                for x in range(self.grid_size):
                    idx = y*self.grid_size + x
                    num = str(idx+1)

                    # Center the box in the cell
                    cell_rect = QtCore.QRect(x*cell_w, y*cell_h, cell_w, cell_h)
                    box_w, box_h = box_size, box_size
                    box_x = cell_rect.center().x() - box_w//2
                    box_y = cell_rect.center().y() - box_h//2
                    box_rect = QtCore.QRect(box_x, box_y, box_w, box_h)
                    # Draw black box
                    painter.setPen(QtCore.Qt.NoPen)
                    painter.setBrush(QtGui.QColor(0, 0, 0))
                    painter.drawRect(box_rect)
                    # Draw white number
                    painter.setPen(QtGui.QColor(255,255,255))
                    painter.setBrush(QtCore.Qt.NoBrush)
                    painter.drawText(box_rect, QtCore.Qt.AlignCenter, num)


    def get_cell_geometry(self, x, y):
        cell_w, cell_h = self.width() // self.grid_size, self.height() // self.grid_size
        top_left = self.mapToGlobal(QtCore.QPoint(0, 0))
        gx = top_left.x() + x * cell_w
        gy = top_left.y() + y * cell_h
        return QtCore.QRect(gx, gy, cell_w, cell_h)


    @QtCore.Slot(int, int, int, int, int)
    def resize_to_rect(self, gx, gy, gw, gh, level):
        """Resize overlay to an absolute global rectangle (precomputed by caller).
        This avoids using the overlay's current size as the basis for further
        subdivisions which can cause iterative shrinking and tiny geometries.
        """
        self.level = level
        rect = QtCore.QRect(gx, gy, gw, gh)
        self.setGeometry(rect)
        self.update()
        self.ensure_above_taskbar()


    @QtCore.Slot()
    def reset(self):
        self.level = 0
        self.resize_screen()
        self.update()
        self.ensure_above_taskbar()


    def ensure_above_taskbar(self):
        QtCore.QTimer.singleShot(10, self.raise_)
