import inspect
import importlib
import os
import threading
import time
from collections import deque
from enum import Enum
from rapidfuzz import fuzz, process, utils
from commands.base_command import BaseCommand

# from commands.ai_assistant.ai_assistant import AiAssistant

class Event(Enum):
    COMMAND_DETECTED = 1
    WAKE_SLEEP = 2

class SubEvent(Enum):
    WAKE = 3
    SLEEP = 4

class CommandDispatcher:

    def __init__(self, settings, translator):
        self.translator = translator
        self.settings = settings
        self.command_subscribers = set()
        self.wake_sleep_subscribers = set()
        
        # all commands dynamically loaded from commands folder
        self.commands = []
        # possible current command that has grabbed the context
        # and has higher priority or needs exit command to leave
        self.current_context_owner = None

        # deque used as a simple thread-safe-ish queue for incoming texts
        # Access to it is protected by self.queue_lock
        self.queue = deque()
        self.queue_lock = threading.Lock()
        self.stop_event = threading.Event()
        # worker thread that will process arrivals
        self.worker = threading.Thread(target=self.worker_loop, daemon=True)
        self.worker.start()

        self.is_active = False

        # DEBUG:
        # self.wake()
        #all = self.get_asr_word_guide()
        #print(all)


    def set_systems(self, asr_system, tts_system):
        self.asr_system = asr_system        
        self.text_to_speech = tts_system


    def get_tts_system(self):
        return self.text_to_speech


    def sleep(self):
        self.is_active = False
        # clean up the current context owner, if any
        if self.current_context_owner:
            self.current_context_owner.exit_context(None)
            self.current_context_owner = None
            self.asr_system.set_free_mode(False)
        self.notify_wake_sleep_subscribers(SubEvent.SLEEP)


    def wake(self):
        self.is_active = True
        self.notify_wake_sleep_subscribers(SubEvent.WAKE)


    def subscribe(self, event, callback):
        """Subscribe a callable to events.        
        The COMMAND_DETECTED callback will be called as callback(text, command)
        
        The WAKE_SLEEP callback will be called as callback(SubEvent) 
        """
        if event == Event.COMMAND_DETECTED:
            self.command_subscribers.add(callback)
        elif event == Event.WAKE_SLEEP:
            self.wake_sleep_subscribers.add(callback)      


    def get_asr_word_guide(self):
        """
        Can be used for ASR to inject as hotwords or prompt.
        """
        all_words = []
        for cmd in self.commands:
            cmd_texts = self.translator.get_command_texts(cmd.name)
            tokens = cmd_texts["asr_guide"]
            all_words.extend(tokens.split(","))

        all_words = list(set(all_words))
        return all_words
   
   
    def get_descriptions(self):
        all_descriptions = []
        ordered_cmds = sorted(self.commands, key=lambda x: x.order)
        for cmd in ordered_cmds:
            cmd_texts = self.translator.get_command_texts(cmd.name)
            desc = cmd_texts["description"]
            all_descriptions.append(desc)

        return all_descriptions


    def notify_text_subscribers(self, text, command):
        for cb in self.command_subscribers:
            try:
                cb(text, command)
            except Exception as e:
                # Protect dispatcher from exceptions in user callbacks
                print(f"Error in command subscriber callback: {e}")


    def notify_wake_sleep_subscribers(self, event):
        for cb in self.wake_sleep_subscribers:
            try:
                cb(event)
            except Exception as e:
                # Protect dispatcher from exceptions in user callbacks
                print(f"Error in wake/sleep event subscriber callback: {e}")


    def load_all_commands(self):
        """Dynamically import all modules in the `commands` package
        and instantiate every class that subclasses BaseCommand.
        """
        package_name = "commands"
        # discover modules in the package and in first-level subpackages
        package = importlib.import_module(package_name)

        prefix = package.__name__ + "."
        modules_to_inspect = []

        # Walk the package directories on disk and import any .py modules
        # we find. This ensures modules that haven't been imported yet
        # (for example modules in subfolders) are actually loaded so
        # their classes can be inspected.
        for pkg_path in package.__path__:
            if not os.path.isdir(pkg_path):
                continue

            for root, _, files in os.walk(pkg_path):
                for fname in files:
                    if not fname.endswith(".py"):
                        continue
                    if fname == "__init__.py":
                        # skip package marker
                        continue
                    full_path = os.path.join(root, fname)

                    # compute module name relative to the package path
                    rel_path = os.path.relpath(full_path, pkg_path)
                    mod_parts = rel_path.replace(os.path.sep, ".")[:-3]  # strip .py
                    modname = prefix + mod_parts
                    try:
                        mod = importlib.import_module(modname)
                        modules_to_inspect.append(mod)
                    except Exception as e:
                        print(f"Failed to import module {modname}: {e}")
                        # skip modules that fail to import
                        continue

        # inspect gathered modules for BaseCommand subclasses
        for mod in modules_to_inspect:
            for _, obj in inspect.getmembers(mod, inspect.isclass):
                # only consider subclasses of BaseCommand defined in this module
                if not (issubclass(obj, BaseCommand) and obj is not BaseCommand):                    
                    continue

                # ignore classes that were imported into this module from elsewhere
                obj_mod = obj.__module__
                if obj_mod != mod.__name__:
                    print(f"Skipping already imported {obj}")
                    continue

                try:
                    inst = obj(self.settings, self.translator, self)
                    self.commands.append(inst)
                except Exception as e:
                    print(f"Failed to instantiate module: {e}")
                    # skip this command if instantiation fails
                    continue


    def on_text_arrived(self, text):
        # push to the right of deque (newest)
        with self.queue_lock:
            self.queue.append(text)


    # in some cases a context holder might decide by itself
    # to release context without a matching exit word
    def release_context(self):
        self.current_context_owner = None
        self.asr_system.set_free_mode(False)


    # the main dispatch logic
    def handle(self, text):

        # the highest priority for the context owner
        # allow only while active or if the command can override sleep
        if self.current_context_owner and (self.is_active or self.current_context_owner.override_sleep):
            texts = self.translator.get_command_texts(self.current_context_owner.name)
            # was it exit word, if had exit at all?
            tokens = texts.get("exit_context")
            if tokens is not None:
                match = CommandDispatcher.find_match(text, tokens)
                if match:
                    self.current_context_owner.exit_context(match)
                    self.notify_text_subscribers(text, f"{self.current_context_owner.name}.exit")
                    # clean up
                    self.current_context_owner = None
                    self.asr_system.set_free_mode(False)
                    return
            
            # was it an activation word again?
            # it is allowed to reactivate a command with another keyword
            # (e.g. to reset state or use multiple sub contexts)
            activated = self.activate_if_match(self.current_context_owner, text)
            if activated:
                return

            ctx_words = [x for x in texts if x.startswith("in_context.")]

            # not exit word, not reactivation, or command does not have special exit
            # go through context words and try to find a match
            # but some commands accept all words for context (e.g. dictation), 
            # except the exit word
            if not ctx_words:
                self.current_context_owner.in_context(None, text)
                return

            for ctxkey in ctx_words:
                tokens = texts[ctxkey]
                match = CommandDispatcher.find_match(text, tokens)
                if match:
                    self.current_context_owner.in_context(ctxkey, match)
                    self.notify_text_subscribers(text, f"{self.current_context_owner.name}.{ctxkey}")
                    return

            if not self.current_context_owner.leaves_context_automatic:
                return

        # if got here, we have active context and were not allowed to leave            
        # ---------- end of context owner priority processing -------------

        # If got here, we are allowed to check all commands
        # and deactivate self.current_context_owner if it was set.
        # It is also OK to reactivate a command that was already active,
        # in case user forgot what context they are in.
        for cmd in self.commands:
            # allow only while active or if the command can override sleep
            if not self.is_active and not cmd.override_sleep:
                continue
            activated = self.activate_if_match(cmd, text)
            if activated:
                return


    def activate_if_match(self, cmd, text):
        cmd_texts = self.translator.get_command_texts(cmd.name)
        act_words = [x for x in cmd_texts if x.startswith("activate.")]
        ctx_words = [x for x in cmd_texts if x.startswith("in_context.")]
        for actkey in act_words:
            tokens = cmd_texts[actkey]
            match = CommandDispatcher.find_match(text, tokens)
            if match:
                # exit and remove the current owner - it did not exist or was automatic-exitable
                if self.current_context_owner:
                    self.current_context_owner.exit_context(None)
                self.current_context_owner = None                    
                # check if need to grab context by the new owner
                if cmd.needs_context:
                    self.current_context_owner = cmd
                    # check if accepts free form text
                    if not ctx_words:
                        self.asr_system.set_free_mode(True)

                cmd.activate(actkey, match)
                self.notify_text_subscribers(text, f"{cmd.name}.activate")
                return True
        
        return False


    def worker_loop(self):
        while True:
            item = None
            with self.queue_lock:
                if self.queue:
                    item = self.queue.popleft()
            if item is None:
                # nothing to process; yield CPU for a short time
                time.sleep(0.01)
                continue

            try:
                self.handle(item)
            except Exception as e:
                print(f"Error in command dispatcher worker: {e}")


    def boot(self):
        # load_all_commands is heavy
        # but we cannot background it into a thread
        # because initialize_ui_dependencies must run on the main UI thread
        # so we cannot avoid locking the UI
        # and should display a splashscreen in any case
        self.load_all_commands()
        self.initialize_ui_dependencies()


    # this must be run from the main App thread
    def initialize_ui_dependencies(self):
        for cmd in self.commands:
            cmd.boot()


    def shut_down(self):
        for cmd in self.commands:
            cmd.shut_down()


    @staticmethod
    def find_match(text, tokens):
        """
        As ASR can seriously misrecognize short texts,
        apply fuzzy matching to select the best command,
        if any.
        """
        toks_list = tokens.split(",")

        score_cutoff = 75

        # Use rapidfuzz's default preprocessor to normalize strings (lowercase, remove
        # diacritics and punctuation) which matches how token lists are stored.
        # Extract the best score above cutoff or nothing.

        # We don't want partial_ratio here
        # to avoid finding cases when one string is partially included,
        # so cannot use WRatio.
        # Using QRatio for Indel similarity (the same as the Levenshtein distance with substitutions weighted as 2.)
        res = process.extractOne(text, toks_list, 
                        scorer=fuzz.QRatio, 
                        processor=utils.default_process, 
                        score_cutoff=score_cutoff)
        
        # print(f"QRatio for '{text}' : '{tokens}' {res}")
        if not res:
            return None

        match = res[0]
        return match

