import bpy
import json
import hashlib
from pathlib import Path
from bpy.types import Operator
from .keymap import KEYMAP_GROUPS, get_hotkey_entry_item


EXCLUDED_KEYS = {
    "bl_idname",
    "colors",
    "preference_section",
    "backup_filepath",
    "last_backup_time",
    "settings_restored",
}


def get_prefs():
    return bpy.context.preferences.addons[__package__].preferences


def get_pref_checksum(data):
    try:
        json_str = json.dumps(data, sort_keys=True)
        return hashlib.md5(json_str.encode('utf-8')).hexdigest()
    except Exception as e:
        print(f"[Checksum Error] {e}")
        return ""


class PreferencesManager:
    """Handles preferences and keymap backup/restore operations"""

    def __init__(self, context):
        self.context = context
        self.prefs = get_prefs()
        self.version = "1.7.0"

    def get_backup_filepath(self):
        """Get the backup file path"""
        backup_filepath = bpy.path.abspath(self.prefs.backup_filepath)
        return Path(backup_filepath) / "preferences_backup.json"

    def get_default_filepath(self):
        """Get the default preferences file path"""
        addon_dir = Path(__file__).parent
        return addon_dir / "default_preferences.json"

    def collect_preferences(self):
        """Collect current preferences data"""
        keys = [
            prop.identifier for prop in self.prefs.bl_rna.properties
            if not prop.is_readonly and prop.identifier not in EXCLUDED_KEYS
        ]

        pref_data = {}
        for key in keys:
            value = getattr(self.prefs, key)
            if isinstance(value, bpy.types.bpy_prop_array):
                value = list(value)
            pref_data[key] = value

        return pref_data

    def collect_keymap_data(self):
        """Collect current keymap settings"""
        wm = self.context.window_manager
        kc = wm.keyconfigs.user
        km = kc.keymaps.get("Text")

        keymap_data = []
        if not km:
            return keymap_data

        for group in KEYMAP_GROUPS:
            group_data = {"label": group["label"], "items": []}

            for item in group["items"]:
                kmi = get_hotkey_entry_item(km, item)
                if kmi:
                    keymap_item = {
                        "operator": item["operator"],
                        "type": kmi.type,
                        "value": kmi.value,
                        "ctrl": kmi.ctrl,
                        "shift": kmi.shift,
                        "alt": kmi.alt
                    }

                    if "properties" in item:
                        keymap_item["properties"] = {}
                        for prop_name in item["properties"].keys():
                            if hasattr(kmi.properties, prop_name):
                                keymap_item["properties"][prop_name] = getattr(
                                    kmi.properties, prop_name)

                    group_data["items"].append(keymap_item)

            keymap_data.append(group_data)

        return keymap_data

    def create_backup_data(self):
        """Create complete backup data structure"""
        pref_data = self.collect_preferences()
        return {
            "addon_version": self.version,
            "checksum": get_pref_checksum(pref_data),
            "preferences": pref_data,
            "keymap": self.collect_keymap_data(),
        }

    def save_backup(self, filepath):
        """Save backup data to file"""
        data = self.create_backup_data()
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, 'w') as file:
            json.dump(data, file, indent=4)

    def load_data_from_file(self, filepath):
        """Load and parse data from backup file"""
        with open(filepath, 'r') as file:
            data = json.load(file)

        # Handle both new and old formats
        if isinstance(data, dict) and "preferences" in data:
            # New format with separate preferences and keymap
            return data["preferences"], data.get("keymap", [])
        else:
            # Old format (just preferences)
            return data, []

    def restore_preferences(self, pref_data):
        """Restore preferences from data"""
        restored_count = 0
        for key, value in pref_data.items():
            if key not in EXCLUDED_KEYS and hasattr(self.prefs, key):
                try:
                    setattr(self.prefs, key, value)
                    restored_count += 1
                except Exception as e:
                    print(f"Failed to restore preference '{key}': {e}")
        return restored_count

    def restore_keymap(self, keymap_data):
        """Restore keymap settings from data"""
        if not keymap_data:
            return 0

        wm = self.context.window_manager
        kc = wm.keyconfigs.user
        km = kc.keymaps.get("Text")

        if not km:
            return 0

        restored_count = 0
        for group_data in keymap_data:
            group_label = group_data["label"]

            # Find the corresponding group in KEYMAP_GROUPS
            for group in KEYMAP_GROUPS:
                if group["label"] == group_label:
                    for saved_item in group_data["items"]:
                        # Find the corresponding item in the group
                        for item in group["items"]:
                            if item["operator"] == saved_item["operator"]:
                                kmi = get_hotkey_entry_item(km, item)

                                if kmi:
                                    self._update_keymap_item(kmi, saved_item)
                                    restored_count += 1

        return restored_count

    def _update_keymap_item(self, kmi, saved_item):
        """Update a single keymap item with saved values"""
        kmi.type = saved_item["type"]
        kmi.value = saved_item["value"]
        kmi.ctrl = saved_item["ctrl"]
        kmi.shift = saved_item["shift"]
        kmi.alt = saved_item["alt"]

        # Restore custom properties if they exist
        if "properties" in saved_item:
            for prop_name, prop_value in saved_item["properties"].items():
                if hasattr(kmi.properties, prop_name):
                    try:
                        setattr(kmi.properties, prop_name, prop_value)
                    except Exception as e:
                        print(
                            f"Failed to restore keymap property '{prop_name}': {e}")

    def compare_with_backup(self, filepath):
        """Compare current state with backup file"""
        if not filepath.exists():
            return False

        try:
            backup_prefs, backup_keymap = self.load_data_from_file(filepath)
            current_prefs = self.collect_preferences()
            current_keymap = self.collect_keymap_data()

            prefs_differ = current_prefs != backup_prefs
            keymap_differ = current_keymap != backup_keymap

            return prefs_differ or keymap_differ
        except Exception as e:
            print(f"[Compare Error] {e}")
            return True


class TEXTIFY_OT_backup_preferences(Operator):
    bl_idname = "textify.backup_preferences"
    bl_label = "Backup Preferences"
    bl_description = "Backup addon preferences and keymap settings"

    def execute(self, context):
        try:
            manager = PreferencesManager(context)
            filepath = manager.get_backup_filepath()
            manager.save_backup(filepath)

            self.report(
                {'INFO'}, f"Preferences and keymap settings backed up to {filepath}")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Failed to backup preferences: {e}")
            return {'CANCELLED'}


class TEXTIFY_OT_restore_preferences(Operator):
    bl_idname = "textify.restore_preferences"
    bl_label = "Restore Preferences"
    bl_description = "Restore addon preferences and keymap settings"

    @classmethod
    def poll(cls, context):
        try:
            manager = PreferencesManager(context)
            filepath = manager.get_backup_filepath()
            return manager.compare_with_backup(filepath)
        except Exception as e:
            print(f"[Restore Poll Error] {e}")
            return True

    def execute(self, context):
        try:
            manager = PreferencesManager(context)
            filepath = manager.get_backup_filepath()

            if not filepath.exists():
                self.report({'ERROR'}, f"Backup file not found: {filepath}")
                return {'CANCELLED'}

            pref_data, keymap_data = manager.load_data_from_file(filepath)

            # Restore preferences and keymap
            pref_count = manager.restore_preferences(pref_data)
            keymap_count = manager.restore_keymap(keymap_data)

            message = f"Restored {pref_count} preferences"
            if keymap_count > 0:
                message += f" and {keymap_count} keymap items"
            message += f" from {filepath}"

            self.report({'INFO'}, message)
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Failed to restore preferences: {e}")
            return {'CANCELLED'}


class TEXTIFY_OT_restore_default_settings(Operator):
    bl_idname = "textify.restore_default_settings"
    bl_label = "Restore Default Settings"
    bl_description = "Reset all preferences to their default values"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        try:
            manager = PreferencesManager(context)
            filepath = manager.get_default_filepath()

            if not filepath.exists():
                self.report(
                    {'ERROR'}, f"Default settings file not found: {filepath}")
                return {'CANCELLED'}

            pref_data, keymap_data = manager.load_data_from_file(filepath)

            # Restore default preferences and keymap
            pref_count = manager.restore_preferences(pref_data)
            keymap_count = manager.restore_keymap(keymap_data)

            message = f"Reset {pref_count} preferences"
            if keymap_count > 0:
                message += f" and {keymap_count} keymap items"
            message += " to default values"

            self.report({'INFO'}, message)
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Failed to reset preferences: {e}")
            return {'CANCELLED'}

    def draw(self, context):
        layout = self.layout
        layout.label(
            text="This will reset all preferences to default!", icon='ERROR')
        layout.label(text="This action cannot be undone.")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)


classes = [
    TEXTIFY_OT_backup_preferences,
    TEXTIFY_OT_restore_preferences,
    TEXTIFY_OT_restore_default_settings,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
