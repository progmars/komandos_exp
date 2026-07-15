import yaml

CONFIG_FILE = "settings.yaml"
CONFIG_FILE_DEV = "settings.dev.yaml"

class Settings:
    def __init__(self, env):
        self.env = env        
        self.config_file = CONFIG_FILE_DEV if self.env == "dev" else CONFIG_FILE
        self.load_settings()


    def load_settings(self):
        self.settings = {}
        try:
            with open(self.config_file, "r") as f:
                self.settings = yaml.safe_load(f)
        except Exception as e:
            print(f"Error loading settings: {e}")


    def get_setting(self, key, default=None):
        return self.settings.get(key, default)


    def get_sidebar_settings(self):

        saved_position = self.get_setting("position", "left")
        saved_direction = self.get_setting("direction", "vertical")

        # sanity check with defaults
        if saved_direction == "horizontal":
            if saved_position not in ("top", "bottom"):
                saved_position = "top"

        if saved_direction == "vertical":
            if saved_position not in ("left", "right"):
                saved_position = "left"

        return (saved_direction, saved_position)


    def save_settings(self):
        try:
            with open(self.config_file, "w") as f:
                yaml.dump(self.settings, f, default_flow_style=False)
        except Exception as e:
            print(f"Error saving settings: {e}")


    def save_setting(self, key, value):
        self.settings[key] = value
        self.save_settings()            