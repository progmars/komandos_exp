import threading
import numpy as np
import pyautogui
import easyocr
from rapidfuzz import fuzz, process, utils
from PySide6 import QtCore
from commands.base_command import BaseCommand
from commands.text_navigator.nav_overlay import NavOverlay
import time

class TextNavigator(BaseCommand):

    def __init__(self, settings, translator, command_dispatcher):
        super().__init__(settings, translator, command_dispatcher)
        self.name = "text_navigator"
        self.order = 7
        self.needs_context = True
        self.leaves_context_automatic = True
        # the overlay is created on the main app thread in boot()
        self.overlay = None

        langs = ["en"]
        cl = translator.current_language
        if cl != "en":
            langs.append(cl)

        # load the model to memory
        self.reader = easyocr.Reader(langs)
        self.last_ocr_result = None


    def activate(self, *_):
        self.last_ocr_result = None

        # Offload screenshot + OCR to a background thread so activate() returns quickly.
        def ocr_worker():
            screenshot = pyautogui.screenshot()
            # screenshot is PIL, OCR needs numpy
            npimg = np.array(screenshot)
            start = time.perf_counter()

            # 1.7s colored 720p
            # optimizations from AI, not yet sure if correct
            result = self.reader.readtext(npimg,
                mag_ratio=1.5,           # Slightly enlarge to catch small UI fonts
                canvas_size=2560,        # Prevent downscaling (set higher for 4k)
                contrast_ths=0.05,       # Skip unnecessary contrast checks
                adjust_contrast=0.5,     # Default is usually fine if check passes
            )

            end = time.perf_counter()
            ocr_time_ms = (end - start) * 1000.0
            print(ocr_time_ms)
            self.last_ocr_result = result

            # send results to overlay if available (thread-safe)
            if self.overlay:
                # use Qt's queued connection to call the slot on the GUI thread
                QtCore.QMetaObject.invokeMethod(
                    self.overlay,
                    "set_ocr_results",
                    QtCore.Qt.QueuedConnection,
                    QtCore.Q_ARG('QVariant', result)
                )
                QtCore.QMetaObject.invokeMethod(self.overlay, "show", QtCore.Qt.QueuedConnection)

        t = threading.Thread(target=ocr_worker, daemon=True)
        t.start()


    def in_context(self, _, text):
        if self.last_ocr_result is None:
            return
        
        # self.last_ocr_result is the result from easyocr
        # Now we need to find the single best matching bounding box with text
        # based on results from find_match()
        # which accepts the text and a simple list of all texts
        # from easyocr

        # build list of OCR texts
        # x[1] is the text part
        options = [x[1] for x in self.last_ocr_result]

        # find best matching OCR text
        match = TextNavigator.find_match(text, options)
        if not match:
            return

        # collect candidate indices with the same normalized text
        candidates = []
        for item in self.last_ocr_result:
            opt = item[1] # text
            if opt == match:
                candidates.append(item)

        if not candidates:
            return

        # if multiple matches, take the first one
        best = candidates[0]

        # compute center of bounding box
        bbox = best[0]
        xs = [float(p[0]) for p in bbox]
        ys = [float(p[1]) for p in bbox]
        center_x = int(sum(xs) / len(xs))
        center_y = int(sum(ys) / len(ys))

        # move mouse to center if computed
        pyautogui.moveTo(center_x, center_y)

        # if we found something, release context to allow clicking
        self.command_dispatcher.release_context()
        self.exit_context(None)


    def exit_context(self, _):
        if self.overlay:
            # safe cross-thread calling
            QtCore.QMetaObject.invokeMethod(self.overlay, "hide", QtCore.Qt.QueuedConnection)


    def boot(self):
        # boot is called the main app thread
        self.overlay = NavOverlay()


    def shut_down(self):
        if self.overlay:
            self.overlay.close()
            self.overlay.deleteLater()
        self.overlay = None


    @staticmethod
    def find_match(text, options_list):
        score_cutoff = 75
        # this time we want WRatio to match inclusions
        # as long as they are unique
        res = process.extractOne(text, options_list, 
                        scorer=fuzz.WRatio, 
                        processor=utils.default_process, 
                        score_cutoff=score_cutoff)
        

        if not res:
            return None

        match = res[0]
        return match

