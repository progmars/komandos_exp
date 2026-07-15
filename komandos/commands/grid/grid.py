from commands.base_command import BaseCommand
import pyautogui
from PySide6 import QtCore
from commands.grid.grid_overlay import GridOverlay

NUMBER_WORDS = {
    "in_context.one": 1, "in_context.two": 2, "in_context.three": 3, "in_context.four": 4, "in_context.five": 5, 
    "in_context.six": 6, "in_context.seven": 7, "in_context.eight": 8, "in_context.nine": 9
}

MAX_NESTING = 4
GRID_XY_SIZE = 3

class Grid(BaseCommand):

    def __init__(self, settings, translator, command_dispatcher):
        super().__init__(settings, translator, command_dispatcher)
        self.name = "grid"
        self.order = 5
        self.needs_context = True
        self.leaves_context_automatic = True
        # the overlay is created on the main app thread in boot()
        self.overlay = None
        self.nesting = 0
        self.cell_stack = []
        # geometry of the full initial overlay area (root)
        self.root_geometry = None



    def activate(self, *_):
        # safe cross-thread calling
        QtCore.QMetaObject.invokeMethod(self.overlay, "reset", QtCore.Qt.QueuedConnection)
        QtCore.QMetaObject.invokeMethod(self.overlay, "show", QtCore.Qt.QueuedConnection)
        self.nesting = 0
        self.cell_stack = []
        # store the root geometry (screen) for absolute calculations
        self.root_geometry = self.overlay.geometry()


    def in_context(self, key, _):

        try:
            if key == "in_context.back":
                if self.nesting > 0:
                    self.nesting -= 1
                    self.cell_stack.pop()
                    self.resize()
                
                return
            
            # was not back, cannot step deeper if max reached
            if self.nesting >= MAX_NESTING:
                return
            
            idx = NUMBER_WORDS.get(key)
            
            x = (idx - 1) % GRID_XY_SIZE
            y = (idx - 1) // GRID_XY_SIZE

            self.cell_stack.append((x, y))
            self.nesting += 1

            center_x, center_y = self.resize()
            pyautogui.moveTo(center_x, center_y)

        except Exception as e:
            print(f"Failed to process grid: {e}")
            return


    # resize and get center
    def resize(self):

        # Compute absolute coordinates from the stored root geometry.
        if self.root_geometry is None:
            geo = self.overlay.geometry()
        else:
            geo = self.root_geometry

        gx = geo.x()
        gy = geo.y()
        gw = geo.width()
        gh = geo.height()

        for cx, cy in self.cell_stack:
            # compute cell size for this level
            cell_w = gw // GRID_XY_SIZE
            cell_h = gh // GRID_XY_SIZE
            gx += cx * cell_w
            gy += cy * cell_h
            gw = cell_w
            gh = cell_h

        center_x = gx + gw // 2
        center_y = gy + gh // 2

        # Call new resize_to_rect slot with absolute global rect
        QtCore.QMetaObject.invokeMethod(
            self.overlay,
            "resize_to_rect",
            QtCore.Qt.QueuedConnection,
            QtCore.Q_ARG(int, gx),
            QtCore.Q_ARG(int, gy),
            QtCore.Q_ARG(int, gw),
            QtCore.Q_ARG(int, gh),
            QtCore.Q_ARG(int, self.nesting)
        )

        return (center_x, center_y)


    def exit_context(self, _):
        if self.overlay:
            # safe cross-thread calling
            QtCore.QMetaObject.invokeMethod(self.overlay, "hide", QtCore.Qt.QueuedConnection)
            QtCore.QMetaObject.invokeMethod(self.overlay, "reset", QtCore.Qt.QueuedConnection)
        self.nesting = 0
        self.cell_stack = []


    def boot(self):
        # safe - on the main app thread
        self.overlay = GridOverlay(grid_size=GRID_XY_SIZE)
        # DEBUG grid sizing
        """       
        self.activate(None)
        self.in_context("seven", None)
        self.in_context("one", None)
        self.in_context("back", None)
        self.in_context("one", None)
        self.in_context("three", None)        
        self.in_context("three", None)
        self.in_context("back", None)
        self.in_context("back", None)
        self.in_context("back", None)
        self.in_context("back", None)
        self.in_context("back", None)
        """


    def shut_down(self):
        if self.overlay:
            self.overlay.close()
            self.overlay.deleteLater()
        self.overlay = None