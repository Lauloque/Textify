import bpy
import rna_keymap_ui


KEYMAP_GROUPS = [
    {
        "label": "Addon Installer",
        "items": [
            {
                "operator": "textify.install_addon_popup",
                "type": "F2", "value": "PRESS",
                "ctrl": False, "shift": False, "alt": False
            },
            {
                "operator": "textify.install_addon",
                "type": "F2", "value": "PRESS",
                "ctrl": False, "shift": False, "alt": True
            },
        ]
    },
    {
        "label": "Bookmarks Line",
        "items": [
            {
                "operator": "bookmark_line.popup",
                "type": "F4", "value": "PRESS",
                "ctrl": False, "shift": False, "alt": False
            },
        ]
    },
    {
        "label": "Code Map",
        "items": [
            {
                "operator": "code_map.popup",
                "type": "ACCENT_GRAVE", "value": "PRESS",
                "ctrl": False, "shift": False, "alt": False
            },
        ]
    },
    {
        "label": "Find & Replace",
        "items": [
            {
                "operator": "text.find_replace",
                "type": "F1", "value": "PRESS",
                "ctrl": False, "shift": False, "alt": False
            },
            {
                "operator": "text.find_previous",
                "type": "D", "value": "PRESS",
                "ctrl": False, "shift": False, "alt": True
            },
            {
                "operator": "text.find",
                "type": "F", "value": "PRESS",
                "ctrl": False, "shift": False, "alt": True
            },
        ]
    },
    {
        "label": "Go to Definition",
        "items": [
            {
                "operator": "textify.go_to_definition",
                "type": "F12", "value": "PRESS",
                "ctrl": False, "shift": False, "alt": False
            },
        ]
    },
    {
        "label": "Open Recent",
        "items": [
            {
                "operator": "textify.open",
                "type": "O", "value": "PRESS",
                "ctrl": True, "shift": False, "alt": False
            },
            {
                "operator": "textify.save",
                "type": "S", "value": "PRESS",
                "ctrl": True, "shift": False, "alt": False
            },
            {
                "operator": "textify.save_as",
                "type": "S", "value": "PRESS",
                "ctrl": True, "shift": True, "alt": False
            },
            {
                "operator": "wm.call_menu",
                "type": "O", "value": "PRESS",
                "ctrl": True, "shift": False, "alt": True,
                "properties": {
                    "name": "TEXTIFY_MT_open_recent",
                }
            },
        ]
    },
    {
        "label": "Script Switcher",
        "items": [
            {
                "operator": "textify.cycle_scripts",
                "type": "TAB", "value": "PRESS",
                "ctrl": True, "shift": False, "alt": False
            },
        ]
    },
    {
        "label": "Script Formatter",
        "items": [
            {
                "operator": "textify.format_script",
                "type": "F", "value": "PRESS",
                "ctrl": True, "shift": True, "alt": False
            },
        ]
    },
]


# to keep track of the custom keymaps this addon adds to Blender.
keys = []


def get_hotkey_entry_item(km, item):
    kmi_name = item["operator"]

    for km_item in km.keymap_items:
        if km_item.idname != kmi_name:
            continue

        # If the item specifies properties, make sure all match
        if "properties" in item:
            match = True
            for prop_name, prop_value in item["properties"].items():
                if not hasattr(km_item.properties, prop_name):
                    match = False
                    break
                if getattr(km_item.properties, prop_name) != prop_value:
                    match = False
                    break
            if not match:
                continue

        return km_item

    return None


def draw_keymap_ui(layout, context):
    col = layout.column()
    kc = context.window_manager.keyconfigs.user

    for group in KEYMAP_GROUPS:
        col.separator(factor=0.4)
        col.label(text=group["label"])
        col.separator(factor=0.2)

        keymap_name = group.get("keymap", "Text")
        km = kc.keymaps.get(keymap_name)
        if not km:
            continue

        for item in group["items"]:
            kmi = get_hotkey_entry_item(km, item)
            if kmi:
                col.context_pointer_set("keymap", km)
                rna_keymap_ui.draw_kmi([], kc, km, kmi, col, 0)


def register_keymap():
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if not kc:
        return

    for group in KEYMAP_GROUPS:
        # Use appropriate keymap based on the operator
        keymap_name = "Text"
        if group["label"] == "Search Window":
            keymap_name = "Window"

        km = kc.keymaps.get(keymap_name)
        if not km:
            km = kc.keymaps.new(
                name=keymap_name, space_type='EMPTY' if keymap_name == "Window" else 'TEXT_EDITOR')

        for item in group["items"]:
            kmi = km.keymap_items.new(
                idname=item["operator"],
                type=item["type"],
                value=item["value"],
                ctrl=item.get("ctrl", False),
                shift=item.get("shift", False),
                alt=item.get("alt", False)
            )

            if "properties" in item:
                for prop_name, prop_value in item["properties"].items():
                    setattr(kmi.properties, prop_name, prop_value)

            kmi.active = True
            keys.append((km, kmi))


def unregister_keymap():
    for km, kmi in keys:
        km.keymap_items.remove(kmi)
    keys.clear()
