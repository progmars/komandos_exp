from PySide6 import QtWidgets, QtCore, QtGui
import numpy as np


class LevelBar(QtWidgets.QWidget):
    """A compact input level meter widget.

    Zones:
    - 0-10%: yellow (too quiet)
    - 10-95%: green (acceptable)
    - 95-100%: red (clipping)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._level = 0  # 0-100
        self.setMinimumHeight(24)


    def set_level(self, value):
        """Set current level and schedule repaint.
        Expect value to be the NumPy array
        dtype float32 with values in -1..1,
        shape (frames, channels) or (frames,)).
        """
        #print(value)
        # If None or empty -> silence
        if value is None:
            v = 0
        elif isinstance(value, np.ndarray):
            data = value
            if data.size == 0:
                v = 0
            else:
                # Compute RMS across all samples and channels
                # Use float64 for stability;
                # float32 in -1..1 range so denom = 1.0.
                # arr = data.astype(np.float64, copy=False)
                # rms = float(math.sqrt(float(np.mean(np.square(arr)))))
                # peak works better to detect overloads, 
                # RMS normalizes too low even when blowing into the mic
                peak = data.max()
                result = peak
                # Map RMS (0..1) to percent (0..100).
                v = int(min(100.0, result * 100.0))

        # clamp and update
        if v < 0:
            v = 0
        if v > 100:
            v = 100
        self._level = v
        # print(v)
        self.update()


    def paintEvent(self, _):
        painter = QtGui.QPainter(self)
        rect = self.rect().adjusted(2, 2, -2, -2)

        # draw background
        painter.setPen(QtGui.QPen(QtGui.QColor('#cccccc')))
        painter.setBrush(QtGui.QBrush(QtGui.QColor('#f5f5f5')))
        painter.drawRect(rect)

        # draw zones: yellow (0-30), green (30-95), red (95-100)
        # Behavior: zones are drawn muted by default, and the area up to the
        # current level is painted with the bright (saturated) variant so
        # reached level appears bright while the rest stays muted.
        total_w = rect.width()
        y_zone = rect.top()
        h_zone = rect.height()

        def zone_rect(start_pct, end_pct):
            x = rect.left() + int(total_w * (start_pct / 100.0))
            w = max(1, int(total_w * ((end_pct - start_pct) / 100.0)))
            return QtCore.QRect(x, y_zone, w, h_zone)

        muted_yellow = QtGui.QColor('#7f6000')
        bright_yellow = QtGui.QColor('#f0c419')
        muted_green = QtGui.QColor('#1f4b1f')
        bright_green = QtGui.QColor('#4caf50')
        muted_red = QtGui.QColor('#7a1717')
        bright_red = QtGui.QColor('#e53935')

        painter.setPen(QtCore.Qt.NoPen)

        # draw muted full zones, add a small overlap to mask some edge glitches
        painter.setBrush(QtGui.QBrush(muted_yellow))
        z_yellow = zone_rect(0, 11)
        painter.drawRect(z_yellow)

        painter.setBrush(QtGui.QBrush(muted_green))
        z_green = zone_rect(10, 96)
        painter.drawRect(z_green)

        painter.setBrush(QtGui.QBrush(muted_red))
        z_red = zone_rect(95, 101)
        painter.drawRect(z_red)

        # compute reached area and draw bright overlays only for that area
        level_w = int(total_w * (self._level / 100.0))
        if level_w > 0:
            level_rect = QtCore.QRect(rect.left(), rect.top(), level_w, rect.height())
            # yellow zone bright overlay
            inter = z_yellow.intersected(level_rect)
            if inter.width() > 0:
                painter.setBrush(QtGui.QBrush(bright_yellow))
                painter.drawRect(inter)

            # green zone bright overlay
            inter = z_green.intersected(level_rect)
            if inter.width() > 0:
                painter.setBrush(QtGui.QBrush(bright_green))
                painter.drawRect(inter)

            # red zone bright overlay
            inter = z_red.intersected(level_rect)
            if inter.width() > 0:
                painter.setBrush(QtGui.QBrush(bright_red))
                painter.drawRect(inter)

        # draw indicator line
        ind_x = rect.left() + level_w
        pen = QtGui.QPen(QtGui.QColor('#222222'))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawLine(ind_x, rect.top(), ind_x, rect.bottom())

