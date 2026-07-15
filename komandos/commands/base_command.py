from abc import ABC

"""
A command can be run-once (needs_context=False) or with a context
that will be grabbed when activate is called.
If context is grabbed, no other commands will be processed 
until this one leaves with exit_context;
unless leaves_context_automatic is set to True - 
then any other matching command will leave the context of this command.

Needs the following texts in i18n:

description - description and guide for the user

asr_guide - to guide ASR to recognize correct words for all commands (do not collect all aliases but only the correct ones)

activate.[key] list
To deal with ASR or user using aliases, multiple words can be supported
Additional keys are optional.
in case the command needs to be activated in different ways (e.g. mouse or keyboard actions).

exit_context - optional, if has context without leaves_context_automatic:
- Optional words for context-specific keys.

in_context.[key] list - optional keyed words to detect for in-context commands.

"""
class BaseCommand(ABC):

    def __init__(self, settings, translator, command_dispatcher):
        self.translator = translator
        self.command_dispatcher = command_dispatcher
        self.override_sleep = False
        # must match folder name, not class name
        self.name = ""
        self.needs_context = False
        self.order = 9999999 # mostly for display in Help, to show more important commands first.
        self.leaves_context_automatic = False
        # if set to None, this will signal that it accepts any text
        # and would allow free-form dictation

    def activate(self, key, word):
        pass

    def in_context(self, key, word):
        pass

    def exit_context(self, word):
        pass  

    # boot and shut_down are on called the main app thread
    # other calls may be called from other threads
    def boot(self):
        pass

    def shut_down(self):
        pass