
from commands.base_command import BaseCommand
import subprocess
import sys

class Run(BaseCommand):

    def __init__(self, settings, translator, command_dispatcher):
        super().__init__(settings, translator, command_dispatcher)
        self.name = "run"
        self.order = 6
        self.needs_context = True
        self.leaves_context_automatic = True


    def in_context(self, key, _):
        try:
            # cannot use . in commands because of translation keys
            # preprocessing
            name = key.replace("in_context.","").replace("_",".")
            if sys.platform == "win32":   
                # most commands on Windows need "start" for OS to find them automatically
                # empty quotes are important for opening objects with default apps
                name = f"start \"\" \"{name}\""

            print(f"Launching {name}...")
            subprocess.Popen(name, shell=True)
        except Exception as e:
            print(f"Failed to start command '{name}': {e}")
            return

    # no special exit needed

