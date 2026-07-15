"""Translation loader and helper used across the application.

Provides a small Translator class that loads YAML files from the package's
`i18n` directory and exposes a `t(key)` lookup with English fallback.
"""
import os
import glob
import yaml


class Translator:
    def __init__(self, current_language="en"):
        self.translations = {}
        self.default_language = "em"
        self.current_language = current_language
        self.load_translations()


    def load_translations(self):
        """Load YAML translation files from the configured i18n directory."""

        root_translations_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "i18n"))
        pattern = os.path.join(root_translations_dir, "*.yaml")
        for path in glob.glob(pattern):
            with open(path, 'r', encoding='utf-8') as fh:
                data = yaml.safe_load(fh) or {}
                code = os.path.splitext(os.path.basename(path))[0]
                self.translations[code] = data

        # Also scan command-specific i18n files under commands/*/i18n/<lang>.yaml
        # Determine commands dir relative to package root
        pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        commands_dir = os.path.join(pkg_root, "commands")

        # commands/*/i18n/*.yaml
        cmd_pattern = os.path.join(commands_dir, "*", "i18n", "*.yaml")
        for path in glob.glob(cmd_pattern):
            with open(path, 'r', encoding='utf-8') as fh:
                data = yaml.safe_load(fh) or {}
                # language code is filename without extension
                code = os.path.splitext(os.path.basename(path))[0]
                # command folder name is the parent of the i18n dir
                command_folder = os.path.basename(os.path.dirname(os.path.dirname(path)))
                # ensure language map exists
                lang_map = self.translations.setdefault(code, {})
                # ensure command namespace exists
                cmd_ns = lang_map.setdefault('command', {})
                # merge under command.<command_folder>
                cmd_ns[command_folder] = data


    def get_command_texts(self, command):
        """Return flattened mapping for `command` inside the `command` namespace for
        the current language.
        """
        lang_map = self.translations.get(self.current_language, {})
        cmd_ns = lang_map.get('command', {})
        val = cmd_ns.get(command)

        if val is None:
            return None

        if isinstance(val, dict):
            flat = Translator.flatten(val)
            return flat

        return val


    @staticmethod
    def flatten(mapping, parent_key=""):
        out = {}
        if not isinstance(mapping, dict):
            return out
        for k, v in mapping.items():
            new_key = f"{parent_key}.{k}" if parent_key else k
            if isinstance(v, dict):
                out.update(Translator.flatten(v, new_key))
            else:
                out[new_key] = v
        return out


    def set_language(self, code):
        self.current_language = code


    def available_languages(self):
        """Return mapping code -> language display name (or code if not set)."""
        out = {}
        for code, data in self.translations.items():
            out[code] = data.get("language_name", code)
        return out


    def t(self, key):
        """Translate dotted key with fallback to English and a humanized key."""
        def lookup(mapping, parts):
            cur = mapping
            for p in parts:
                if not isinstance(cur, dict):
                    return None
                
                cur = cur.get(p)
                if cur is None:
                    return None
                
            return cur

        parts = key.split(".") if isinstance(key, str) else [key]

        # try current language
        lang_map = self.translations.get(self.current_language, {})
        v = lookup(lang_map, parts)
        if v is not None:
            return v

        # fallback to default (english)
        if self.current_language != self.default_language:
            en_map = self.translations.get(self.default_language, {})
            v = lookup(en_map, parts)
            if v is not None:
                return v

        # last resort: humanize
        return key.replace("_", " ").capitalize()
