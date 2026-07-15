from commands.base_command import BaseCommand
import pyautogui
from enum import Enum

# how much to move in a single step
SCREEN_PERCENTAGE = 0.01

class Direction(Enum):
    UP = 1
    DOWN = 2
    LEFT = 3
    RIGHT = 4

class MouseMove(BaseCommand):

    def __init__(self, settings, translator, command_dispatcher):
        super().__init__(settings, translator, command_dispatcher)
        self.name = "mouse_move"
        self.order = 3
        self.needs_context = True
        self.leaves_context_automatic = True


    def activate(self, key, _):
        direction = MouseMove.key_to_direction(key)
        MouseMove.move(direction)


    def in_context(self, key, _):
        direction = MouseMove.key_to_direction(key)
        MouseMove.move(direction)


    def key_to_direction(key):
        key = key.replace("activate.", "")
        if key == "up":
            return Direction.UP
        if key == "down":
            return Direction.DOWN
        if key == "left":
            return Direction.LEFT
        if key == "right":
            return Direction.RIGHT


    def move(direction):
        try:
            screen_w, screen_h = pyautogui.size()
            cur_x, cur_y = pyautogui.position()

            step_x = int(screen_w * SCREEN_PERCENTAGE)
            step_y = int(screen_h * SCREEN_PERCENTAGE)

            dx = 0
            dy = 0

            if direction == Direction.LEFT:
                dx = -step_x
            elif direction == Direction.RIGHT:
                dx = step_x
            elif direction == Direction.UP:
                dy = -step_y
            elif direction == Direction.DOWN:
                dy = step_y
            else:
                return

            new_x = max(0, min(screen_w - 1, cur_x + dx))
            new_y = max(0, min(screen_h - 1, cur_y + dy))

            # moveTo is absolute; set duration=0 for instant movement
            pyautogui.moveTo(new_x, new_y, duration=0)
        except Exception:
            return