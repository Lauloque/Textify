if "bpy" in locals():
    import importlib
    importlib.reload(addon_installer)
    importlib.reload(bookmark_line)
    importlib.reload(convert_case)
    importlib.reload(character_count)
    importlib.reload(code_map)
    importlib.reload(find_replace)
    importlib.reload(highlight_occurrences)
    importlib.reload(jump_to_line)
    importlib.reload(reveal_in_explorer)
    importlib.reload(trim_whitespace)
    importlib.reload(script_formatter)
    importlib.reload(open_recent)
else:
    from . import addon_installer
    from . import bookmark_line
    from . import convert_case
    from . import character_count
    from . import code_map
    from . import find_replace
    from . import highlight_occurrences
    from . import jump_to_line
    from . import reveal_in_explorer
    from . import trim_whitespace
    from . import script_formatter
    from . import open_recent
    import bpy


submodules = [
    open_recent,
    addon_installer,
    bookmark_line,
    convert_case,
    character_count,
    code_map,
    find_replace,
    highlight_occurrences,
    jump_to_line,
    reveal_in_explorer,
    script_formatter,
    trim_whitespace,
]


def register():
    for mod in submodules:
        mod.register()


def unregister():
    for mod in reversed(submodules):
        try:
            mod.unregister()
        except Exception as e:
            print(f"Error unregistering submodule {mod.__name__}: {e}")
