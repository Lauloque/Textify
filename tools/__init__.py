if "bpy" in locals():
    import importlib
    importlib.reload(bookmark_line)
    importlib.reload(convert_case)
    importlib.reload(character_count)
    importlib.reload(code_map)
    importlib.reload(find_replace)
    importlib.reload(go_to_definition)
    importlib.reload(highlight_occurrences)
    importlib.reload(jump_to_line)
    importlib.reload(reveal_in_explorer)
    importlib.reload(trim_whitespace)
    importlib.reload(script_formatter)
    importlib.reload(script_switcher)
    importlib.reload(open_recent)
    importlib.reload(addon_installer)
else:
    from . import bookmark_line
    from . import convert_case
    from . import character_count
    from . import code_map
    from . import find_replace
    from . import go_to_definition
    from . import highlight_occurrences
    from . import jump_to_line
    from . import reveal_in_explorer
    from . import trim_whitespace
    from . import script_formatter
    from . import script_switcher
    from . import open_recent
    from . import addon_installer


submodules = [
    bookmark_line,
    convert_case,
    character_count,
    code_map,
    find_replace,
    go_to_definition,
    highlight_occurrences,
    jump_to_line,
    open_recent,
    reveal_in_explorer,
    script_formatter,
    script_switcher,
    trim_whitespace,
    addon_installer,
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
