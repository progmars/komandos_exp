"""i18n package initializer exposing a shared Translator instance.

Importing `translator` and `t` from this package gives a ready-to-use Translator singleton.
Example: from komandos.i18n import translator
         t('tabs.audio')
"""
from .translator import Translator

# create a shared translator instance that other modules can import
translator = Translator()

# and a convenience wrapper
t = translator.t

__all__ = ["translator", "Translator", "t"]
