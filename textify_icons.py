from pathlib import Path
from bpy.utils import previews

_custom_icons = None

def load_icons():
    global _custom_icons
    if _custom_icons is None:
        _custom_icons = previews.new()

        icons_dir = Path(__file__).resolve().parent / "icons"
        for icon_file in icons_dir.glob("*.png"):
            icon_name = icon_file.stem  # filename without extension
            if icon_name not in _custom_icons:
                _custom_icons.load(icon_name, str(icon_file), 'IMAGE')


def unload_icons():
    global _custom_icons
    if _custom_icons:
        previews.remove(_custom_icons)
        _custom_icons = None


def get_icon(name):
    if _custom_icons is None:
        load_icons()
    return _custom_icons.get(name)
