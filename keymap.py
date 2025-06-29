import bpy


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
        ]
    },
]


# to keep track of the custom keymaps this addon adds to Blender.
keys = []


def get_hotkey_entry_item(km, item):
    kmi_name = item["operator"]

    for i, km_item in enumerate(km.keymap_items):
        if km.keymap_items.keys()[i] == kmi_name:
            if "prop_name" in item:
                kmi_value = item["prop_name"]
                if km.keymap_items[i].properties.name == kmi_value:
                    return km_item
            return km_item
    return None  # not needed, since no return means None, but keeping for readability


def draw_keymap_ui(layout, context):
    import rna_keymap_ui

    col = layout.column()
    kc = context.window_manager.keyconfigs.user

    for group in KEYMAP_GROUPS:
        col.separator(factor=0.4)
        col.label(text=group["label"])
        col.separator(factor=0.2)

        km = kc.keymaps.get("Text")
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
        km = kc.keymaps.get("Text")
        if not km:
            km = kc.keymaps.new(name="Text", space_type='TEXT_EDITOR')

        for item in group["items"]:
            kmi = km.keymap_items.new(
                idname=item["operator"],
                type=item["type"],
                value=item["value"],
                ctrl=item.get("ctrl", False),
                shift=item.get("shift", False),
                alt=item.get("alt", False)
            )

            # Set custom properties (e.g., name for wm.call_menu_pie)
            if "properties" in item:
                for prop_name, prop_value in item["properties"].items():
                    setattr(kmi.properties, prop_name, prop_value)

            kmi.active = True
            keys.append((km, kmi))


def unregister_keymap():
    for km, kmi in keys:
        km.keymap_items.remove(kmi)
    keys.clear()

