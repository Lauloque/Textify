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


if "bpy" in locals():
    import importlib
    importlib.reload(tools)
    importlib.reload(ops)
    importlib.reload(keymap)
    importlib.reload(textify_icons)
else:
    from . import tools
    from . import ops
    from . import keymap
    from . import textify_icons
    from .tools import highlight_occurrences
    from .keymap import KEYMAP_GROUPS, get_hotkey_entry_item
    import bpy

import json

from pathlib import Path
from bpy.props import StringProperty, BoolProperty, EnumProperty, IntProperty, FloatVectorProperty, FloatProperty


github_icon = textify_icons.get_icon("github")
discord_icon = textify_icons.get_icon("discord")
highlight_icon = textify_icons.get_icon("highlight")


# -------------------------------------------------------------
#                           Function
# -------------------------------------------------------------


def auto_restore_prefs():
    """Auto-restore preferences on startup (runs once)"""
    prefs = bpy.context.preferences.addons[__package__].preferences
    backup_path = Path(bpy.path.abspath(prefs.backup_filepath))
    filepath = backup_path / "preferences_backup.json"

    if filepath.exists() and not prefs.settings_restored:
        try:
            bpy.ops.textify.restore_preferences()
            prefs.settings_restored = True
            print("Textify: Preferences auto-restored successfully")
        except Exception as e:
            print(f"Textify: Failed to auto-restore preferences: {e}")

    # Return None to unregister the timer (run only once)
    return None


def is_module_installed(name):
    try:
        __import__(name)
        return True
    except ImportError:
        return False


# -------------------------------------------------------------
#                       Addon Preferences
# -------------------------------------------------------------


# Define your properties in a dictionary
feature_props = {
    "Addon Installer": "enable_addon_installer",
    "Bookmark Line": "enable_bookmark_line",
    "Case Converter": "enable_case_convert",
    "Character Count": "enable_character_count",
    "Code Map": "enable_code_map",
    "Highlight Occurrences": "enable_highlight_occurrences",
    "Jump to Line": "enable_jump_to_line",
    "Reveal in Explorer ": "enable_open_script_folder",
    "Script Formatter": "enable_script_formatter",
    "Trim Whitespace": "enable_trim_whitespace"
}


def draw_expand_box(layout, prop_name, label, prefs, draw_func=None):
    box = layout.box()
    row = box.row()
    icon = 'TRIA_DOWN' if getattr(prefs, prop_name) else 'TRIA_RIGHT'
    row.prop(prefs, prop_name, icon=icon, text="", emboss=False)
    row.label(text=label)

    if getattr(prefs, prop_name) and draw_func:
        draw_func(box)


def get_last_backup_time(backup_path: str) -> str:
    from datetime import datetime
    if not backup_path:
        return "No path set"

    backup_file = Path(bpy.path.abspath(backup_path)) / \
        "preferences_backup.json"

    if backup_file.exists():
        mod_time = backup_file.stat().st_mtime
        return datetime.fromtimestamp(mod_time).strftime("%Y-%m-%d %I:%M:%S %p")
    else:
        return "No backup file found"


def draw_layout(self, context, items_per_row=3):
    layout = self.layout

    # Convert dict to list o    f (label, prop_name) tuples
    props_list = list(feature_props.items())

    # Split into chunks for each row
    for i in range(0, len(props_list), items_per_row):
        row = layout.row()
        for label, prop_name in props_list[i:i + items_per_row]:
            box = row.box()
            box.prop(self, prop_name, text=label)


def update_sidebar_category(self, context):
    """Change sidebar category of add-ons panels"""

    panel_classes = [
        tools.bookmark_line.BOOKMARK_LINE_PT_Panel,
        tools.code_map.CODE_MAP_PT_panel,
        tools.open_recent.TEXTIFY_PT_open_recent,
    ]

    categories = [
        self.bookmark_line_category,
        self.code_map_category,
        self.open_recent_category,
    ]

    for cls, category in zip(panel_classes, categories):
        try:
            bpy.utils.unregister_class(cls)
        except:
            pass
        cls.bl_category = category
        bpy.utils.register_class(cls)


class TEXTIFY_preferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    # Custom panel category
    bookmark_line_category: StringProperty(
        name="Bookmark Line",
        description="Category to show Bookmark Line panel",
        default="Bookmark Line",
        update=update_sidebar_category,
    )
    code_map_category: StringProperty(
        name="Code Map",
        description="Category to show Code Map panel",
        default="Code Map",
        update=update_sidebar_category,
    )
    open_recent_category: StringProperty(
        name="Open Recent",
        description="Category to show Open Recent panel",
        default="Text",
        update=update_sidebar_category,
    )

    # Enable/Disable features
    enable_addon_installer: BoolProperty(
        name="Enable Addon Installer",
        description=(
            "Create a zip of the current script and install it in one click.\n\n"
            "Location: Text Editor Sidebar > Text > Install Addon.\n"
            "Shortcuts: F2 (Popup install), Alt+F5 (Instant install)"
        ),
        default=True
    )
    enable_script_formatter: BoolProperty(
        name="Enable autopep8 Formatter",
        description=(
            "Enable formatting of the current script using autopep8.\n\n"
            "This feature allows automatic code formatting according to PEP 8 standards "
            "with support for a 120 character max line length and import handling rules.\n\n"
            "Location: Text Editor > Format Menu > Format with autopep8."
        ),
        default=True
    )
    enable_bookmark_line: BoolProperty(
        name="Enable Bookmark Line",
        description=(
            "Bookmark a line in the Text Editor and quickly jump back to it.\n\n"
            "Location: Text Editor Sidebar > Bookmark Line.\n"
            "Shortcut: F4"
        ),
        default=True
    )
    enable_case_convert: BoolProperty(
        name="Enable Case Converter",
        description=(
            "Convert selected text to different cases such as snake_case, camelCase, PascalCase, etc.\n\n"
            "Location: Text Editor Header > Format Menu > Convert Case To"
        ),
        default=True
    )
    enable_character_count: BoolProperty(
        name="Enable Character Count",
        description=(
            "Displays total character count, and current line and column number of the cursor.\n\n"
            "Location: Text Editor Footer"
        ),
        default=True
    )
    enable_code_map: BoolProperty(
        name="Enable Code Map",
        description=(
            "Code Map is a code navigation tool to explore and jump between classes, functions, variables, and properties.\n\n"
            "Location: Text Editor Sidebar > Code Map.\n"
            "Shortcut: ` (Backtick)"
        ),
        default=True
    )
    enable_find_replace: BoolProperty(
        name="Enable Find & Replace",
        description=(
            "Improved find with find previous and total match count.\n\n"
            "Location: Text Editor Sidebar > Text > Find & Replace.\n"
            "Shortcut: F1"
        ),
        default=True
    )
    enable_highlight_occurrences: BoolProperty(
        name="Enable Highlight Occurrences",
        description=(
            "Highlights all matches of the selected text."
        ),
        default=True,
        update=highlight_occurrences.update_highlight
    )
    enable_jump_to_line: BoolProperty(
        name="Enable Jump to Line",
        description=(
            "Jump to a specific line directly from the text editor header.\n\n"
            "Click and drag the slider to scrub through the lines."
        ),
        default=True
    )
    enable_open_script_folder: BoolProperty(
        name="Enable Reveal in Explorer Shortcut",
        description=(
            "Enable a button in the text editor footer to open the current script's folder\n"
            "in the system file explorer.\n\n"
            "Requires the script to be saved to a file."
        ),
        default=True
    )
    enable_trim_whitespace: BoolProperty(
        name="Enable Trim Whitespace",
        description=(
            "Trim leading and trailing whitespace\n\n"
            "This option can be accessed from the context menu."
        ),
        default=True
    )

    # Addon Installer preferences
    zip_name_style: bpy.props.EnumProperty(
        name="Zip Name Style",
        description="Choose how the addon zip file is named.",
        items=[
            ('NAME_ONLY', "Name Only", "Example: my_addon.zip"),
            ('NAME_UNDERSCORE_VERSION', "Name_Version", "Example: my_addon_1.0.zip"),
            ('NAME_DASH_VERSION', "Name-Version", "Example: my_addon-1.0.zip"),
        ],
        default='NAME_DASH_VERSION'
    )
    addon_installer_popup_width: bpy.props.IntProperty(
        name="Popup Width",
        description="Adjust the width of the Addon Installer popup dialog",
        default=400,
        min=200,
        max=800,
        step=10,
        subtype='PIXEL',
    )

    # Bookmark Line preferences
    show_bookmark_line_panel: BoolProperty(
        name="Show Bookmark Line Panel",
        description="Show or hide the Bookmark Line panel",
        default=True,
    )

    # Code Map preferences
    auto_activate_search: BoolProperty(
        name="Auto Activate Search",
        description="Enable or disable auto-activation of search when invoking popup",
        default=False
    )
    show_code_filters: BoolProperty(
        name="Show Code Filters in Panel",
        description=(
            "Toggle to display the code components (Classes, Variables, Functions, "
            "Class Functions, Properties) in the Code Map panel and popup"
        ),
        default=True,
    )
    show_code_map_panel: BoolProperty(
        name="Show Code Map Panel",
        description="Show or hide the Open Recent panel",
        default=True,
    )
    code_map_popup_width: IntProperty(
        name="Popup Width",
        description="Adjust the width of the Code Map popup dialog",
        default=320,
        min=250,
        max=600,
        step=10,
        subtype='PIXEL',
    )

    # Find & replace preferences
    enable_find_set_selected: BoolProperty(
        name="Set Selection for Finding",
        description="If enabled, the selected text will be automatically filled into the 'Find' field when the 'Find & Replace' popup is invoked",
        default=True,
    )
    enable_replace_set_selected: BoolProperty(
        name="Set Selection for Replacement",
        description="If enabled, the selected text will be automatically filled into the 'Replace' field when the 'Find & Replace' popup is invoked",
        default=True,
    )
    auto_activate_find: BoolProperty(
        name="Auto Activate Find",
        description="Enable or disable auto-activation of find field when invoking popup",
        default=False,
    )

    # Hightlight Occurrences preferences
    highlight_mode: bpy.props.EnumProperty(
        name="Highlight Mode",
        items=[
            ('AUTO', "Auto", "Use selection if no find text is given"),
            ('SELECTION', "Selection", "Only highlight selected text"),
            ('FIND_TEXT', "Find Text", "Only highlight find text"),
        ],
        default='FIND_TEXT'
    )
    colors = {
        "BLUE": ((0.25, 0.33, 0.45, 1), (1, 1, 1, 1), (0.18, 0.44, 0.61, 1), (0.14, 0.6, 1, 0.55)),
        "RED": ((0.58, 0.21, 0.21, 1), (1, 1, 1, 1), (0.64, 0.27, 0.27, 1), (1, 0.21, 0.21, 0.5)),
        "GREEN": ((0.24, 0.39, 0.26, 1), (1, 1, 1, 1), (0.2, 0.5, 0.19, 1), (0.04, 1.0, 0.008, 0.4)),
        "YELLOW": ((0.39, 0.38, 0.07, 1), (1, 1, 1, 1), (0.46, 0.46, 0, 1), (1, 0.79, 0.09, 0.4)),

        # Additional colors:
        "PURPLE": ((0.38, 0.29, 0.55, 1), (1, 1, 1, 1), (0.48, 0.37, 0.64, 1), (0.69, 0.46, 1.0, 0.5)),
        "ORANGE": ((0.6, 0.32, 0.1, 1), (1, 1, 1, 1), (0.72, 0.41, 0.16, 1), (1.0, 0.5, 0.1, 0.4)),
        "PINK": ((0.6, 0.25, 0.4, 1), (1, 1, 1, 1), (0.73, 0.3, 0.5, 1), (1.0, 0.4, 0.6, 0.4)),
        "TEAL": ((0.0, 0.5, 0.5, 1), (1, 1, 1, 1), (0.0, 0.65, 0.65, 1), (0.0, 1.0, 1.0, 0.4)),
        "CYAN": ((0.0, 0.65, 0.9, 1), (1, 1, 1, 1), (0.0, 0.75, 1.0, 1), (0.2, 0.9, 1.0, 0.4)),
        "GRAY": ((0.3, 0.3, 0.3, 1), (1, 1, 1, 1), (0.4, 0.4, 0.4, 1), (0.5, 0.5, 0.5, 0.4)),
    }
    col_preset: EnumProperty(
        name="Color Presets",
        description="Highlight color presets",
        default="BLUE",
        update=highlight_occurrences.update_colors,
        items=(
            ("BLUE", "Blue", "", 1),
            ("RED", "Red", "", 2),
            ("GREEN", "Green", "", 3),
            ("YELLOW", "Yellow", "", 4),
            ("PURPLE", "Purple", "", 5),
            ("ORANGE", "Orange", "", 6),
            ("PINK", "Pink", "", 7),
            ("TEAL", "Teal", "", 8),
            ("CYAN", "Cyan", "", 9),
            ("GRAY", "Gray", "", 10),
            ("CUSTOM", "Custom", "", 11),
        )
    )
    line_thickness: IntProperty(
        name="Line Thickness",
        description="Line Thickness",
        default=1,
        min=1,
        max=4
    )
    min_str_len: IntProperty(
        name='Minimum Search Length',
        description="Don't search below this",
        default=2,
        min=1,
        max=4
    )
    font_size_comp: IntProperty(
        name='Font size compensation',
        description="Highlighted words font size compensation if UI scale changed",
        default=0,
        min=-2,
        max=2
    )
    col_bg: FloatVectorProperty(
        name='Background',
        description='Background color',
        default=colors['BLUE'][0],
        subtype='COLOR',
        size=4,
        min=0,
        max=1
    )
    col_line: FloatVectorProperty(
        name='Line / Frame',
        description='Line and frame color',
        default=colors['BLUE'][2],
        subtype='COLOR',
        size=4,
        min=0,
        max=1
    )
    fg_col: FloatVectorProperty(
        name='Foreground',
        description='Foreground color',
        default=colors['BLUE'][1],
        size=4,
        min=0,
        max=1,
        subtype='COLOR'
    )
    col_scroll: FloatVectorProperty(
        name="Scrollbar",
        description="Scroll highlight opacity",
        default=colors['BLUE'][3],
        size=4,
        min=0,
        max=1,
        subtype='COLOR'
    )
    draw_type: EnumProperty(
        name="Draw Type",
        description="Draw type for highlights",
        default="SOLID",
        items=(
            ("SOLID", "Solid", "", 1),
            ("LINE", "Line", "", 2),
            ("FRAME", "Frame", "", 3),
            ("SOLID_FRAME", "Solid + Frame", "", 4)
        )
    )
    scroll_horiz_pos: FloatProperty(
        name="Horizontal Offset",
        description="Scrollbar markers horizontal offset",
        default=0.0,
        min=0.0,
        max=10.0,
        # update=highlight_occurrences.update_highlight
    )
    scroll_marker_length: FloatProperty(
        name="Length",
        description="Scrollbar markers length",
        default=6.0,  # Default value in pixels
        min=1.0,
        max=100.0,
        # update=highlight_occurrences.update_highlight
    )
    col_scroll_selected: FloatVectorProperty(
        description="Scrollbar color for selected word",
        name="Scrollbar (Selected)",
        default=(1.0, 0.5, 0.0, 1.0),
        size=4,
        min=0,
        max=1,
        subtype='COLOR'
    )

    # Open recent preferences
    recent_data_path: StringProperty(
        name="Recent File Data Path",
        description="Directory to store recent file history",
        subtype='DIR_PATH',
        default=bpy.utils.user_resource('SCRIPTS')
    )
    show_open_recent_panel: BoolProperty(
        name="Show Open Recent Panel",
        description="Show or hide the Open Recent panel",
        default=True,
    )
    show_folder_name: BoolProperty(
        name="Show Folder Name for '__init__.py'",
        description="Displays the folder name for '__init__.py' files instead of the file name itself",
        default=True,
    )
    max_entries: IntProperty(
        name="Max Recent Files",
        description="Maximum number of recent files to keep",
        default=30,
        min=5,
        max=1000
    )
    backup_filepath: StringProperty(
        name="Backup Filepath",
        subtype='FILE_PATH',
        default=str(Path.home() / "Documents" / "textify"),
    )

    last_backup_time: StringProperty(
        name="Last Backup Time",
        default="Never"
    )
    settings_restored: BoolProperty(default=False)

    expand_addon_installer: BoolProperty(
        name="Expand Addon Installer", default=False)
    expand_script_formatter: BoolProperty(
        name="Expand Script Formatter", default=False)
    expand_bookmark: BoolProperty(name="Expand Bookmark", default=False)
    expand_code_map: BoolProperty(name="Expand Code Map", default=False)
    expand_find_replace: BoolProperty(
        name="Expand Find & Replace", default=False)
    expand_highlight_occurrences: BoolProperty(
        name="Expand Highlight Occurrences", default=False)
    expand_open_recent: BoolProperty(name="Expand Open Recent", default=False)
    expand_category: BoolProperty(name="Expand Category", default=False)

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

        row = layout.row()
        row.prop(self, "preference_section", expand=True)

        if self.preference_section == 'TOOLS':
            draw_layout(self, context, items_per_row=2)

            layout.use_property_split = True
            layout.use_property_decorate = False

            self.draw_category(layout)

            if self.enable_addon_installer:
                self.draw_settings_addon_installer(layout)

            if self.enable_bookmark_line:
                self.draw_settings_bookmark_line(layout)

            if self.enable_code_map:
                self.draw_settings_code_map(layout)

            self.draw_settings_find_replace(layout)

            if self.enable_highlight_occurrences:
                self.draw_settings_highlight_occurrences(layout)

            self.draw_settings_open_recent(layout)

            if self.enable_script_formatter:
                self.draw_settings_script_formatter(layout)

        elif self.preference_section == 'KEYMAP':
            keymap.draw_keymap_ui(layout, context)

        elif self.preference_section == 'SETTINGS':
            # === Backup & Restore ===
            box = layout.box()
            box.label(text="Backup & Restore", icon='FILE_BACKUP')

            # Backup path
            row = box.row()
            row.prop(self, "backup_filepath",
                     text="Backup Path")

            # Backup & Restore buttons
            row = box.row(align=False)
            row.scale_y = 1.3
            row.operator("textify.backup_preferences",
                         text="Backup", icon="EXPORT")
            row.operator("textify.restore_preferences",
                         text="Restore", icon="IMPORT")

            # Last backup timestamp
            last_backup_time = get_last_backup_time(self.backup_filepath)
            row = box.row()
            row.label(text=f"Last Backup: {last_backup_time}", icon='TIME')

            # === Reset Settings ===
            box = layout.box()
            box.label(text="Reset Preferences", icon='LOOP_BACK')
            row = box.row()
            # row.alert = True
            row.operator(
                "textify.restore_default_settings",
                text="Reset All Settings to Default",
                icon="FILE_REFRESH"
            )

        elif self.preference_section == 'ABOUT':
            box = layout.box()
            box.label(text="Product Page", icon='WINDOW')
            box.operator("wm.url_open", text="Blender Extensions",
                         icon='BLENDER').url = "https://extensions.blender.org/add-ons/textify/"
            box.operator("wm.url_open", text="GitHub",
                         icon_value=github_icon.icon_id).url = "https://github.com/Jishnu-jithu/textify"

            box = layout.box()
            box.label(text="Links", icon='DECORATE_LINKED')
            box.operator("wm.url_open", text="Documentation",
                         icon='HELP').url = "https://jishnujithu.gitbook.io/textify"
            box.operator("wm.url_open", text="Join Discord Server",
                         icon_value=discord_icon.icon_id).url = "https://discord.gg/2E8GZtmvYf"

            box = layout.box()
            box.label(text="Feedback", icon='TEXT')
            box.operator("wm.url_open", text="Report a Bug",
                         icon='ERROR').url = "https://discord.com/channels/1356442907338608640/1356460250047189142"
            box.operator("wm.url_open", text="Request a Feature",
                         icon='OUTLINER_OB_LIGHT').url = "https://discord.com/channels/1356442907338608640/1356535534238957668"

    def draw_category(self, layout):
        def draw_content(box):
            if self.enable_bookmark_line and self.show_bookmark_line_panel:
                box.prop(self, "bookmark_line_category")

            if self.enable_code_map and self.show_code_map_panel:
                box.prop(self, "code_map_category")

            box.prop(self, "open_recent_category")

        draw_expand_box(layout, "expand_category",
                        "Panel Cateogry", self, draw_content)

    def draw_settings_addon_installer(self, layout):
        def draw_content(box):
            box.prop(self, "zip_name_style")
            box.prop(self, "addon_installer_popup_width")

        draw_expand_box(layout, "expand_addon_installer",
                        "Addon Installer Settings", self, draw_content)

    def draw_settings_bookmark_line(self, layout):
        def draw_content(box):
            box.prop(self, "show_bookmark_line_panel")

        draw_expand_box(layout, "expand_bookmark",
                        "Bookmark Line Settings", self, draw_content)

    def draw_settings_code_map(self, layout):
        def draw_content(box):
            box.prop(self, "auto_activate_search")
            box.prop(self, "show_code_filters")
            box.prop(self, "show_code_map_panel")
            box.prop(self, "code_map_popup_width")

        draw_expand_box(layout, "expand_code_map",
                        "Code Map Settings", self, draw_content)

    def draw_settings_find_replace(self, layout):
        def draw_content(box):
            box.prop(self, "enable_find_set_selected")
            box.prop(self, "enable_replace_set_selected")
            box.prop(self, "auto_activate_find")

        draw_expand_box(layout, "expand_find_replace",
                        "Find & Replace Settings", self, draw_content)

    def draw_settings_highlight_occurrences(self, layout):
        def draw_content(box):
            tho_props = bpy.context.scene.tho_settings
            sub = box.box()
            sub.label(text="Highlighting Behavior:")
            sub.prop(self, "highlight_mode")
            sub.prop(tho_props, "show_in_scroll")
            sub.prop(tho_props, "case_sensitive")
            sub.prop(tho_props, "whole_word")

            sub = box.box()
            sub.label(text="Scrollbar marker:")
            sub.prop(self, "scroll_horiz_pos")
            sub.prop(self, "scroll_marker_length")

            sub = box.box()
            sub.label(text="Selection search:")
            sub.prop(self, "min_str_len")
            sub.prop(self, "font_size_comp")

            sub = box.box()
            sub.label(text="Draw type:")
            sub.row().prop(self, "draw_type", expand=True)

            col = sub.column()
            col.enabled = self.draw_type in {'LINE', 'FRAME', 'SOLID_FRAME'}
            # col.prop(self, "line_thickness")

            sub = box.box()
            sub.label(text="Color presets:")
            sub.prop(self, "col_preset", expand=False)
            if self.col_preset == 'CUSTOM':
                for item in ["col_bg", "fg_col", "col_line", "col_scroll", "col_scroll_selected"]:
                    sub.column().prop(self, item)

        draw_expand_box(layout, "expand_highlight_occurrences",
                        "Highlight Occurrences Settings", self, draw_content)

    def draw_settings_open_recent(self, layout):
        def draw_content(box):
            box.prop(self, "recent_data_path")
            box.prop(self, "max_entries")
            box.prop(self, "show_open_recent_panel")
            box.prop(self, "show_folder_name")

        draw_expand_box(layout, "expand_open_recent",
                        "Open Recent Settings", self, draw_content)

    def draw_settings_script_formatter(self, layout):
        def draw_content(box):
            box.label(text="Python Module Status", icon='INFO')

            modules = {
                "autopep8": is_module_installed("autopep8"),
                "pycodestyle": is_module_installed("pycodestyle"),
            }

            missing = [name for name, installed in modules.items()
                       if not installed]

            # Compact module status rows
            for name, installed in modules.items():
                icon = 'CHECKMARK' if installed else 'CANCEL'
                box.label(text=f"{name}", icon=icon)

            # Simple warning box if missing
            if missing:
                box = box.box()
                box.alert = True
                box.label(
                    text=f"Missing Python module(s): {', '.join(missing)}", icon='ERROR')

                row = box.row()
                row.operator("text.install_formatter_deps", icon='IMPORT')

        draw_expand_box(layout, "expand_script_formatter",
                        "Script Formatter Settings", self, draw_content)


class TEXTIFY_PT_toggle_popover(bpy.types.Panel):
    bl_label = "Textify"
    bl_idname = "TEXTIFY_PT_toggle_popover"
    bl_space_type = 'TEXT_EDITOR'
    bl_region_type = 'WINDOW'
    bl_ui_units_x = 9

    def draw(self, context):
        layout = self.layout
        prefs = context.preferences.addons[__package__].preferences

        layout.prop(prefs, "enable_addon_installer", text="Addon Installer")
        layout.prop(prefs, "enable_bookmark_line", text="Bookmark Line")
        layout.prop(prefs, "enable_case_convert", text="Case Converter")
        layout.prop(prefs, "enable_character_count", text="Character Count")
        layout.prop(prefs, "enable_code_map", text="Code Map")
        layout.prop(prefs, "enable_highlight_occurrences",
                    text="Highlight Occurrences")
        layout.prop(prefs, "enable_jump_to_line", text="Jump to Line")
        layout.prop(prefs, "enable_open_script_folder",
                    text="Reveal in Explorer")
        layout.prop(prefs, "enable_script_formatter",
                    text="Script Formatter")
        layout.prop(prefs, "enable_trim_whitespace", text="Trim Whitespace")

        layout.operator("preferences.addon_show",
                        text="Open Settings").module = __name__


def add_to_header(self, context):
    layout = self.layout
    layout.popover_group(
        "TEXT_EDITOR", region_type="WINDOW", context="", category="")


classes = [
    TEXTIFY_preferences,
    TEXTIFY_PT_toggle_popover,
]


submodules = [
    tools,
    ops,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    for mod in submodules:
        mod.register()

    bpy.types.TEXT_HT_header.append(add_to_header)

    keymap.register_keymap()
    bpy.app.timers.register(auto_restore_prefs, first_interval=0.1)
    textify_icons.load_icons()


def unregister():
    # Unregister submodules
    for mod in reversed(submodules):
        try:
            mod.unregister()
        except Exception as e:
            print(
                f"Error unregistering submodule {getattr(mod, '__name__', mod)}: {e}")
            import bl_ui.space_text
            import importlib
            importlib.reload(bl_ui.space_text)

    # Unregister classes
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception as e:
            print(
                f"Error unregistering class {getattr(cls, '__name__', cls)}: {e}")

    keymap.unregister_keymap()

    if add_to_header in bpy.types.TEXT_HT_header:
        bpy.types.TEXT_HT_header.remove(add_to_header)

    textify_icons.unload_icons()

    if bpy.app.timers.is_registered(auto_restore_prefs):
        bpy.app.timers.unregister(auto_restore_prefs)
