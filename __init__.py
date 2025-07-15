##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
##### END GPL LICENSE BLOCK #####

import bpy
from bpy.props import StringProperty, BoolProperty, EnumProperty, IntProperty, FloatVectorProperty, FloatProperty
from pathlib import Path
from datetime import datetime

from . import tools, ops, keymap, textify_icons
from .tools import highlight_occurrences

if "bpy" in locals():
    import importlib
    for mod in [tools, ops, keymap, textify_icons]:
        importlib.reload(mod)

from .textify_icons import get_icon


# Configuration data
FEATURE_PROPS = {
    "Addon Installer": ("enable_addon_installer", "Create a zip of the current script and install it in one click.\n\nLocation: Text Editor Sidebar > Text > Install Addon.\nShortcuts: F2 (Popup install), Alt+F5 (Instant install)"),
    "Bookmark Line": ("enable_bookmark_line", "Bookmark a line in the Text Editor and quickly jump back to it.\n\nLocation: Text Editor Sidebar > Bookmark Line.\nShortcut: F4"),
    "Case Converter": ("enable_case_convert", "Convert selected text to different cases such as snake_case, camelCase, PascalCase, etc.\n\nLocation: Text Editor Header > Format Menu > Convert Case To"),
    "Character Count": ("enable_character_count", "Displays total character count, and current line and column number of the cursor.\n\nLocation: Text Editor Footer"),
    "Code Map": ("enable_code_map", "Code Map is a code navigation tool to explore and jump between classes, functions, variables, and properties.\n\nLocation: Text Editor Sidebar > Code Map.\nShortcut: ` (Backtick)"),
    "Go to Definition": ("enable_go_to_definition", "Go to the definition of a function, class, or variable.\n\nLocation: Right-click menu in Text Editor.\nShortcut: Customizable"),
    "Highlight Occurrences": ("enable_highlight_occurrences", "Highlights all matches of the selected text."),
    "Jump to Line": ("enable_jump_to_line", "Jump to a specific line directly from the text editor header.\n\nClick and drag the slider to scrub through the lines."),
    "Script Formatter": ("enable_script_formatter", "Enable formatting of the current script using autopep8.\n\nThis feature allows automatic code formatting according to PEP 8 standards with support for a 120 character max line length and import handling rules.\n\nLocation: Text Editor > Format Menu > Format with autopep8."),
    "Trim Whitespace": ("enable_trim_whitespace", "Trim leading and trailing whitespace\n\nThis option can be accessed from the context menu.")
}

COLOR_PRESETS = {
    "BLUE": ((0.0, 0.4, 0.80, 0.3), (1, 1, 1, 0.7), (0.14, .6, 1, .55)),
    "RED": ((0.58, 0.21, 0.21, 1), (1, 1, 1, 0.8), (1, 0.21, .21, 0.5)),
    "GREEN": ((0.24, 0.39, 0.26, 1), (1, 1, 1, 0.8), (.04, 1., .008, .4)),
    "YELLOW": ((0.39, 0.38, 0.07, 1), (1, 1, 1, 0.8), (1, .79, .09, .4)),
    "ORANGE": ((0.6, 0.32, 0.1, 1), (1, 1, 1, 0.8), (1, 0.5, 0.1, 0.5)),
    "GRAY": ((0.3, 0.3, 0.3, 1), (1, 1, 1, 0.8), (0.5, 0.5, 0.5, 0.5)),
}

PANEL_CLASSES = [
    tools.bookmark_line.BOOKMARK_LINE_PT_Panel,
    tools.code_map.CODE_MAP_PT_panel,
    tools.open_recent.TEXTIFY_PT_open_recent,
]


# Utility functions
def draw_expand_box(layout, prop_name, label, prefs, draw_func=None):
    box = layout.box()
    row = box.row()
    icon = 'TRIA_DOWN' if getattr(prefs, prop_name) else 'TRIA_RIGHT'
    row.prop(prefs, prop_name, icon=icon, text="", emboss=False)
    row.label(text=label)
    if getattr(prefs, prop_name) and draw_func:
        draw_func(box)


def draw_labeled_box(layout, label, draw_func):
    box = layout.box()
    box.label(text=label)
    draw_func(box)


def get_last_backup_time(backup_path: str) -> str:
    if not backup_path:
        return "No path set"
    backup_file = Path(bpy.path.abspath(backup_path)) / "preferences_backup.json"
    if backup_file.exists():
        mod_time = backup_file.stat().st_mtime
        return datetime.fromtimestamp(mod_time).strftime("%Y-%m-%d %I:%M:%S %p")
    return "No backup file found"


def draw_features_layout(self, context, items_per_row=2):
    layout = self.layout
    props_list = list(FEATURE_PROPS.items())
    for i in range(0, len(props_list), items_per_row):
        row = layout.row()
        for label, (prop_name, _) in props_list[i:i + items_per_row]:
            row.box().prop(self, prop_name, text=label)


def update_sidebar_category(self, context):
    categories = [self.bookmark_line_category, self.code_map_category, self.open_recent_category]
    for cls, category in zip(PANEL_CLASSES, categories):
        try:
            bpy.utils.unregister_class(cls)
        except:
            pass
        cls.bl_category = category
        bpy.utils.register_class(cls)


class TEXTIFY_preferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    # Category properties
    bookmark_line_category: StringProperty(
        name="Bookmark Line",
        description="Category to show Bookmark Line panel",
        default="Bookmark Line",
        update=update_sidebar_category
    )
    code_map_category: StringProperty(
        name="Code Map",
        description="Category to show Code Map panel",
        default="Code Map",
        update=update_sidebar_category
    )
    open_recent_category: StringProperty(
        name="Open Recent",
        description="Category to show Open Recent panel",
        default="Text",
        update=update_sidebar_category
    )

    # Feature enable properties
    enable_addon_installer: BoolProperty(
        name="Enable Addon Installer",
        description=FEATURE_PROPS["Addon Installer"][1],
        default=True
    )
    enable_bookmark_line: BoolProperty(
        name="Enable Bookmark Line",
        description=FEATURE_PROPS["Bookmark Line"][1],
        default=True
    )
    enable_case_convert: BoolProperty(
        name="Enable Case Converter",
        description=FEATURE_PROPS["Case Converter"][1],
        default=True
    )
    enable_character_count: BoolProperty(
        name="Enable Character Count",
        description=FEATURE_PROPS["Character Count"][1],
        default=True
    )
    enable_code_map: BoolProperty(
        name="Enable Code Map",
        description=FEATURE_PROPS["Code Map"][1],
        default=True
    )
    enable_go_to_definition: BoolProperty(
        name="Enable Go to Definition",
        description=FEATURE_PROPS["Go to Definition"][1],
        default=True
    )
    enable_highlight_occurrences: BoolProperty(
        name="Enable Highlight Occurrences",
        description=FEATURE_PROPS["Highlight Occurrences"][1],
        default=False,
        update=highlight_occurrences.update_highlight
    )
    enable_jump_to_line: BoolProperty(
        name="Enable Jump to Line",
        description=FEATURE_PROPS["Jump to Line"][1],
        default=True
    )
    enable_script_formatter: BoolProperty(
        name="Enable Script Formatter",
        description=FEATURE_PROPS["Script Formatter"][1],
        default=True
    )
    enable_trim_whitespace: BoolProperty(
        name="Enable Trim Whitespace",
        description=FEATURE_PROPS["Trim Whitespace"][1],
        default=True
    )

    # Settings properties
    zip_name_style: EnumProperty(
        name="Zip Name Style",
        description="Choose how the addon zip file is named.",
        items=[
            ('NAME_ONLY', "Name Only", "Example: my_addon.zip"),
            ('NAME_UNDERSCORE_VERSION', "Name_Version", "Example: my_addon_1.0.zip"),
            ('NAME_DASH_VERSION', "Name-Version", "Example: my_addon-1.0.zip")
        ],
        default='NAME_DASH_VERSION'
    )
    addon_installer_popup_width: IntProperty(
        name="Popup Width",
        description="Adjust the width of the Addon Installer popup dialog",
        default=380,
        min=200,
        max=800,
        step=10,
        subtype='PIXEL'
    )

    auto_activate_search: BoolProperty(
        name="Auto Activate Search",
        description="Enable or disable auto-activation of search when invoking popup",
        default=False
    )
    show_code_filters: BoolProperty(
        name="Show Code Filters in Panel",
        description="Toggle to display the code components in the Code Map panel and popup",
        default=True
    )
    code_map_popup_width: IntProperty(
        name="Popup Width",
        description="Adjust the width of the Code Map popup dialog",
        default=320,
        min=250,
        max=600,
        step=10,
        subtype='PIXEL'
    )

    auto_activate_find: BoolProperty(
        name="Auto Activate Find",
        description="Enable or disable auto-activation of find field when invoking popup",
        default=False
    )
    use_textify_find_replace: BoolProperty(
        name="Use Textify Find & Replace",
        description="Enable or disable the custom Textify Find & Replace button in the UI",
        default=True
    )
    realtime_search: BoolProperty(
        name="Real-Time Highlighting",
        description="Enable/Disable real-time search while typing",
        default=True
    )
    enable_find_on_enter: bpy.props.BoolProperty(
        name="Enable Find on Enter",
        description="Enable running find search automatically when pressing Enter (for non-realtime input)",
        default=True
    )

    highlight_mode: EnumProperty(
        name="Highlight Mode",
        items=[
            ('AUTO', "Auto", "Use selection if no find text is given"),
            ('SELECTION', "Selection", "Only highlight selected text"),
            ('FIND_TEXT', "Find Text", "Only highlight find text")
        ],
        default='FIND_TEXT',
        update=highlight_occurrences.update_highlight
    )

    def update_colors(self, context):
        preset = self.col_preset
        if preset != "CUSTOM":
            bg, fg, scroll = COLOR_PRESETS[preset]
            self.highlight_color = bg
            self.text_color = fg
            self.scroll_color = scroll

    case_sensitive: BoolProperty(
        name="Case Sensitive",
        description="Match case when searching for occurrences",
        default=False
    )
    show_in_scroll: BoolProperty(
        name="Show in Scrollbar",
        description="Show markers in scrollbar",
        default=True
    )
    col_preset: EnumProperty(
        name="Color Preset",
        description="Highlight color presets",
        items=[
            ("BLUE", "Blue", "", 1),
            ("RED", "Red", "", 2),
            ("GREEN", "Green", "", 3),
            ("YELLOW", "Yellow", "", 4),
            ("ORANGE", "Orange", "", 5),
            ("GRAY", "Gray", "", 6),
            ("CUSTOM", "Custom", "", 7)
        ],
        update=update_colors,
        default="BLUE"
    )

    # Color properties
    highlight_color: FloatVectorProperty(
        name="Highlight Color",
        description="Color of the highlight background",
        subtype='COLOR',
        size=4,
        default=(0.25, 0.33, 0.45, .07),
        min=0.0,
        max=1.0
    )
    text_color: FloatVectorProperty(
        name="Text Color",
        description="Color of the highlighted text",
        subtype='COLOR',
        size=4,
        default=(1.0, 1.0, 1.0, 1.0),
        min=0.0,
        max=1.0
    )
    scroll_color: FloatVectorProperty(
        name="Scrollbar Color",
        description="Color of scrollbar markers",
        subtype='COLOR',
        size=4,
        default=(0.14, .6, 1, .5),
        min=0.0,
        max=1.0
    )
    scroll_horiz_pos: FloatProperty(
        name="Horizontal Offset",
        description="Scrollbar markers horizontal offset",
        default=0.0,
        min=0.0,
        max=10.0
    )
    scroll_marker_length: FloatProperty(
        name="Marker Length",
        description="Scrollbar markers length",
        default=6.0,
        min=1.0,
        max=100.0
    )

    # File settings
    recent_data_path: StringProperty(
        name="Recent File Data Path",
        description="Directory to store recent file history",
        subtype='DIR_PATH',
        default=bpy.utils.user_resource('CONFIG')
    )
    show_open_recent_panel: BoolProperty(
        name="Show Open Recent Panel",
        description="Show or hide the Open Recent panel",
        default=True
    )
    show_folder_name: BoolProperty(
        name="Show Folder Name for '__init__.py'",
        description="Displays the folder name for '__init__.py' files instead of the file name itself",
        default=True
    )
    max_entries: IntProperty(
        name="Max Recent Files",
        description="Maximum number of recent files to keep",
        default=30,
        min=3,
        max=50
    )
    backup_filepath: StringProperty(
        name="Backup Filepath",
        subtype='FILE_PATH',
        default=str(Path.home() / "Documents" / "textify")
    )

    # Internal settings
    settings_restored: BoolProperty(
        default=True
    )
    expand_highlight_occurrences: BoolProperty(
        name="Expand Highlight Occurrences",
        default=False
    )
    expand_script_formatter: BoolProperty(
        name="Expand Script Formatter",
        default=False
    )
    preference_section: EnumProperty(
        name="Preference Section",
        description="Select which section to view",
        items=[
            ('TOOLS', "Tools", "View tools settings"),
            ('KEYMAP', "Keymap", "View keymap settings"),
            ('SETTINGS', "Settings", "View general settings"),
            ('ABOUT', "About", "About Textify Addon")
        ],
        default='TOOLS'
    )

    def draw(self, context):
        layout = self.layout
        layout.row().prop(self, "preference_section", expand=True)

        section_methods = {
            'TOOLS': self.draw_tools_section,
            'KEYMAP': lambda layout: keymap.draw_keymap_ui(layout, context),
            'SETTINGS': self.draw_settings_section,
            'ABOUT': self.draw_about_section
        }
        section_methods[self.preference_section](layout)

    def draw_tools_section(self, layout):
        draw_features_layout(self, bpy.context, items_per_row=2)
        layout.use_property_split = True
        layout.use_property_decorate = False

        # Draw all settings sections
        self.draw_category_settings(layout)
        if self.enable_addon_installer:
            self.draw_addon_installer_settings(layout)
        if self.enable_code_map:
            self.draw_code_map_settings(layout)
        self.draw_find_replace_settings(layout)
        self.draw_open_recent_settings(layout)
        if self.enable_highlight_occurrences:
            self.draw_highlight_occurrences_settings(layout)

    def draw_settings_section(self, layout):
        # Backup & Restore
        box = layout.box()
        box.label(text="Backup & Restore", icon='FILE_BACKUP')
        box.prop(self, "backup_filepath", text="Backup Path")
        row = box.row(align=False)
        row.scale_y = 1.3
        row.operator("textify.backup_preferences", text="Backup", icon="EXPORT")
        row.operator("textify.restore_preferences", text="Restore", icon="IMPORT")
        box.label(text=f"Last Backup: {get_last_backup_time(self.backup_filepath)}", icon='TIME')

        # Reset Preferences
        box = layout.box()
        box.label(text="Reset Preferences", icon='LOOP_BACK')
        box.operator("textify.restore_default_settings", text="Reset All Settings to Default", icon="FILE_REFRESH")

    def draw_about_section(self, layout):
        sections = [
            ("Product Page", 'WINDOW', [
                ("Blender Extensions", 'BLENDER', "https://extensions.blender.org/add-ons/textify/"),
                ("GitHub", get_icon("github"), "https://github.com/Jishnu-jithu/textify")
            ]),
            ("Links", 'DECORATE_LINKED', [
                ("Documentation", 'HELP', "https://jishnujithu.gitbook.io/textify"),
                ("Join Discord Server", get_icon("discord"), "https://discord.gg/2E8GZtmvYf")
            ]),
            ("Feedback", 'TEXT', [
                ("Report a Bug", 'ERROR', "https://discord.com/channels/1356442907338608640/1356460250047189142"),
                ("Request a Feature", 'OUTLINER_OB_LIGHT', "https://discord.com/channels/1356442907338608640/1356535534238957668")
            ]),
            ("Support the Project", 'FUND', [
                ("Buy on Gumroad", get_icon("gumroad"), "https://jishnukv.gumroad.com/l/textify")
            ])
        ]

        for title, icon, items in sections:
            box = layout.box()
            box.label(text=title, icon=icon)
            for text, btn_icon, url in items:
                if isinstance(btn_icon, int):  # Custom icon
                    box.operator("wm.url_open", text=text, icon_value=btn_icon).url = url
                else:
                    box.operator("wm.url_open", text=text, icon=btn_icon).url = url

    def draw_category_settings(self, layout):
        box = layout.box()
        box.label(text="Panel Category")
        for prop in ["bookmark_line_category", "code_map_category", "open_recent_category"]:
            if prop != "bookmark_line_category" or self.enable_bookmark_line:
                if prop != "code_map_category" or self.enable_code_map:
                    box.prop(self, prop)

    def draw_addon_installer_settings(self, layout):
        def draw_content(box):
            box.prop(self, "zip_name_style")
            box.prop(self, "addon_installer_popup_width")

        draw_labeled_box(layout, "Addon Installer Settings", draw_content)

    def draw_code_map_settings(self, layout):
        def draw_content(box):
            box.prop(self, "auto_activate_search")
            box.prop(self, "show_code_filters")
            box.prop(self, "code_map_popup_width")

        draw_labeled_box(layout, "Code Map Settings", draw_content)

    def draw_find_replace_settings(self, layout):
        def draw_box_content(box):
            box.prop(self, "auto_activate_find")
            box.prop(self, "use_textify_find_replace")
            
            if self.use_textify_find_replace:
                box.prop(self, "realtime_search")

                if not self.realtime_search:
                    box.prop(self, "enable_find_on_enter")

        draw_labeled_box(layout, "Find & Replace Settings", draw_box_content)

    def draw_open_recent_settings(self, layout):
        def draw_content(box):
            box.prop(self, "recent_data_path")
            box.prop(self, "max_entries")
            box.prop(self, "show_open_recent_panel")
            box.prop(self, "show_folder_name")

        draw_labeled_box(layout, "Open Recent Settings", draw_content)

    def draw_highlight_occurrences_settings(self, layout):
        def draw_content(box):
            sub = box.box()
            sub.label(text="Highlighting Behavior:")
            for prop in ["highlight_mode", "case_sensitive", "show_in_scroll"]:
                sub.prop(self, prop)

            if self.show_in_scroll:
                sub_box = box.box()
                sub_box.label(text="Scrollbar Settings:")
                for prop in ["scroll_horiz_pos", "scroll_marker_length"]:
                    sub_box.prop(self, prop)

            sub.prop(self, "col_preset")
            if self.col_preset == "CUSTOM":
                for prop in ["highlight_color", "text_color", "scroll_color"]:
                    sub.prop(self, prop)

        draw_expand_box(layout, "expand_highlight_occurrences", "Highlight Occurrences Settings", self, draw_content)


class TEXTIFY_PT_toggle_popover(bpy.types.Panel):
    bl_label = "Textify"
    bl_idname = "TEXTIFY_PT_toggle_popover"
    bl_space_type = 'TEXT_EDITOR'
    bl_region_type = 'WINDOW'
    bl_ui_units_x = 9

    def draw(self, context):
        layout = self.layout
        prefs = context.preferences.addons[__package__].preferences

        for label, (prop_name, _) in FEATURE_PROPS.items():
            layout.prop(prefs, prop_name, text=label)

        layout.operator("preferences.addon_show", text="Open Settings").module = __name__


def draw_header(self, context):
    self.layout.popover_group("TEXT_EDITOR", region_type="WINDOW", context="", category="")


classes = [TEXTIFY_preferences, TEXTIFY_PT_toggle_popover]
submodules = [tools, ops, keymap, textify_icons]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    for mod in submodules:
        mod.register()

    bpy.types.TEXT_HT_header.append(draw_header)

    prefs = bpy.context.preferences.addons[__package__].preferences
    prefs.update_colors(bpy.context)


def unregister():
    for mod in reversed(submodules):
        try:
            mod.unregister()
        except Exception as e:
            print(f"Error unregistering submodule {getattr(mod, '__name__', mod)}: {e}")

    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception as e:
            print(f"Error unregistering class {getattr(cls, '__name__', cls)}: {e}")

    bpy.types.TEXT_HT_header.remove(draw_header)
