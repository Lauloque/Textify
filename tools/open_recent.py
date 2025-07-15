import bpy
import shutil

from pathlib import Path
from bpy.app.handlers import persistent
from bpy.props import StringProperty, CollectionProperty, IntProperty, EnumProperty, PointerProperty
from bpy.types import Operator, Menu, PropertyGroup


def get_addon_prefs(context):
    for addon_id in context.preferences.addons.keys():
        if 'textify' in addon_id.lower():
            return context.preferences.addons[addon_id].preferences
    return None


@persistent
def load_post_handler(dummy):
    recent_manager.load_recent_files()

    # Defer UI sync to ensure UI is fully initialized
    def sync_ui_deferred():
        context = bpy.context
        prefs = get_addon_prefs(context)
        if hasattr(context, 'window_manager') and prefs.show_open_recent_panel:
            sync_ui_list(context)
        return None

    # Schedule UI sync for next update cycle
    bpy.app.timers.register(sync_ui_deferred, first_interval=0.1)


def sync_ui_list(context):
    try:
        wm = context.window_manager
        if not hasattr(wm, 'recent_files_props'):
            return

        props = wm.recent_files_props
        props.recent_files.clear()

        for path in recent_manager.get_all_files():
            item = props.recent_files.add()
            item.filepath = path
    except Exception as e:
        print(f"Textify: Error syncing UI list: {e}")


class RecentFileItem(bpy.types.PropertyGroup):
    filepath: StringProperty(name="File Path")


class TEXTIFY_PG_Properties(PropertyGroup):
    active_index: IntProperty()
    recent_files: CollectionProperty(type=RecentFileItem)


class TEXTIFY_UL_recent_files(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        prefs = get_addon_prefs(context)
        filepath = Path(item.filepath)
        exists = filepath.exists()

        # Determine display name
        if prefs.show_folder_name and filepath.name == "__init__.py":
            folder_name = filepath.parent.name.replace(" ", "_")
            display_name = f"{folder_name}.py" if folder_name else "__init__.py"
        else:
            display_name = filepath.name

        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.label(text=display_name,
                      icon='WORDWRAP_ON' if exists else 'ERROR')

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text="", icon='FILE_TEXT')


class RecentFilesManager:
    """Singleton class to manage recent files efficiently"""
    _instance = None
    _recent_files = []

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._initialized = True

    def _ensure_loaded(self):
        if not hasattr(self, 'recent_files_path'):
            self.load_recent_files()

    def load_recent_files(self):
        try:
            prefs = get_addon_prefs(bpy.context)
            base_dir = Path(bpy.path.abspath(prefs.recent_data_path))

            txt_path = base_dir / "open_recent.txt"

            # Handle legacy path in ~/Documents/Open Recent
            old_dir = Path.home() / "Documents" / "Open Recent"
            old_txt_path = old_dir / "open_recent.txt"
            if old_txt_path.exists():
                try:
                    shutil.move(str(old_txt_path), str(txt_path))
                    if old_dir.exists() and not any(old_dir.iterdir()):
                        old_dir.rmdir()
                except Exception as e:
                    print(
                        f"[textify] Warning: Failed to migrate legacy recent file: {e}")

            self.recent_files_path = txt_path

            if txt_path.exists():
                self._recent_files = [
                    str(Path(line.strip()).resolve())
                    for line in txt_path.read_text(encoding='utf-8').splitlines()
                    if line.strip()
                ]
            else:
                self._recent_files = []

        except OSError as e:
            print(f"[textify] Failed to load recent files: {e}")
            self._recent_files = []

    def save_recent_files(self):
        try:
            self._ensure_loaded()
            if hasattr(self, 'recent_files_path'):
                self.recent_files_path.parent.mkdir(
                    parents=True, exist_ok=True)
                content = "\n".join(self._recent_files)
                self.recent_files_path.write_text(content, encoding='utf-8')
            else:
                print("[textify] Warning: recent_files_path not set. Skipping save.")
        except OSError as e:
            print(f"[textify] Error saving recent files: {e}")

    def add_file(self, filepath, reorder=False):
        self._ensure_loaded()
        prefs = get_addon_prefs(bpy.context)

        filepath_str = str(Path(filepath).resolve())

        if filepath_str in self._recent_files:
            if not reorder:
                return  # Already tracked — do nothing
            # Reorder: move it to the top
            self._recent_files.remove(filepath_str)

        self._recent_files.insert(0, filepath_str)

        # Enforce max_entries from addon preferences
        max_len = prefs.max_entries
        self._recent_files = self._recent_files[:max_len]

        self.save_recent_files()

        context = bpy.context
        if hasattr(context, 'window_manager'):
            sync_ui_list(context)

    def get_recent_files(self):
        self._ensure_loaded()  # Ensure data is loaded
        valid_files = []
        invalid_files = []

        for path_str in self._recent_files:
            path = Path(path_str)
            file_entry = {
                'filepath': path_str,
                'filename': path.name
            }

            if path.exists():
                valid_files.append(file_entry)
            else:
                invalid_files.append(file_entry)

        return valid_files, invalid_files

    def get_all_files(self):
        self._ensure_loaded()  # Ensure data is loaded
        return self._recent_files.copy()

    def remove_file(self, filepath):
        self._ensure_loaded()
        filepath_str = str(Path(filepath).resolve())
        self._recent_files = [
            path for path in self._recent_files
            if path != filepath_str
        ]
        self.save_recent_files()

        context = bpy.context
        if hasattr(context, 'window_manager'):
            sync_ui_list(context)

    def remove_missing_files(self):
        self._ensure_loaded()
        self._recent_files = [
            path for path in self._recent_files
            if Path(path).exists()
        ]
        self.save_recent_files()

        context = bpy.context
        if hasattr(context, 'window_manager'):
            sync_ui_list(context)

    def file_exists_in_list(self, filepath):
        self._ensure_loaded()
        filepath_str = str(Path(filepath).resolve())
        return filepath_str in self._recent_files

    def clear_recent_files(self):
        self._recent_files.clear()
        self.save_recent_files()

        # Update UI list
        context = bpy.context
        if hasattr(context, 'window_manager'):
            sync_ui_list(context)

    def swap_files(self, index1, index2):
        self._ensure_loaded()
        if 0 <= index1 < len(self._recent_files) and 0 <= index2 < len(self._recent_files):
            self._recent_files[index1], self._recent_files[index2] = \
                self._recent_files[index2], self._recent_files[index1]
            self.save_recent_files()


# Global manager instance
recent_manager = RecentFilesManager()


class TEXTIFY_OT_open_recent_file(Operator):
    bl_idname = "textify.open_file"
    bl_label = "Open Recent File"
    bl_description = "Open a recent file"

    filepath: StringProperty()

    @classmethod
    def description(cls, context, properties):
        from datetime import datetime, timedelta
        fp = properties.filepath
        if fp:
            try:
                mtime = Path(fp).stat().st_mtime
                dt = datetime.fromtimestamp(mtime)
                now = datetime.now()
                label = ("Today" if dt.date() == now.date()
                         else "Yesterday" if dt.date() == (now - timedelta(days=1)).date()
                         else dt.strftime("%d %b %Y"))
                return f"{fp}\n\nModified: {label} {dt.strftime('%I:%M %p')}"
            except FileNotFoundError:
                return f"File not found: {fp}"
            except Exception as e:
                return f"Error retrieving file info: {e}"
        return "Open Text"

    def execute(self, context):
        if not self.filepath or not Path(self.filepath).exists():
            self.report({'ERROR'}, "File not found")
            return {'CANCELLED'}

        try:
            bpy.ops.text.open(filepath=self.filepath)
            recent_manager.add_file(self.filepath, reorder=True)
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to open file: {e}")
            return {'CANCELLED'}


class TEXTIFY_OT_open_file_browser(Operator):
    bl_idname = "textify.open"
    bl_label = "Open Text"
    bl_description = "Open a new text data-block"

    filepath: StringProperty(subtype="FILE_PATH")
    filter_glob: StringProperty(
        default="*.py;*.txt;*.glsl;*.osl;*.lua;*.xml;*.json", options={'HIDDEN'})

    def execute(self, context):
        if not self.filepath:
            return {'CANCELLED'}

        try:
            bpy.ops.text.open(filepath=self.filepath)
            recent_manager.add_file(self.filepath, reorder=True)
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to open file: {e}")
            return {'CANCELLED'}

    def invoke(self, context, event):
        st = context.space_data.text
        if st:
            self.filepath = st.filepath
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class TEXTIFY_OT_save(Operator):
    bl_idname = "textify.save"
    bl_label = "Save"
    bl_description = "Save active text data-block"

    def execute(self, context):
        text = getattr(context.space_data, 'text', None)
        if not text:
            self.report({'ERROR'}, "No text to save")
            return {'CANCELLED'}

        try:
            if text.filepath:
                # Add .py extension if no extension exists
                filepath = Path(text.filepath)
                if not filepath.suffix:
                    new_filepath = filepath.with_suffix('.py')
                    text.filepath = str(new_filepath)

                bpy.ops.text.save()
                recent_manager.add_file(text.filepath)

                self.report({'INFO'}, f"Saved text: {text.filepath}")
            else:
                # If no filepath, invoke save as
                bpy.ops.text.save_as('INVOKE_DEFAULT')
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to save file: {e}")
            return {'CANCELLED'}


class TEXTIFY_OT_save_as(Operator):
    bl_idname = "textify.save_as"
    bl_label = "Save As..."
    bl_description = "Save active text data-block to a new file"

    filepath: StringProperty(subtype="FILE_PATH")
    filter_glob: StringProperty(
        default="*.py;*.txt;*.glsl;*.osl;*.lua;*.xml;*.json", options={'HIDDEN'})

    def execute(self, context):
        if not self.filepath:
            return {'CANCELLED'}

        try:
            # Add .py extension if no extension exists
            filepath = Path(self.filepath)
            if not filepath.suffix:
                filepath = filepath.with_suffix('.py')
                self.filepath = str(filepath)

            bpy.ops.text.save_as(filepath=self.filepath)
            recent_manager.add_file(self.filepath)
            self.report({'INFO'}, f"Saved text as {self.filepath}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to save file: {e}")
            return {'CANCELLED'}

    def invoke(self, context, event):
        st = context.space_data.text
        if st:
            self.filepath = st.filepath
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class TEXTIFY_OT_save_copy(Operator):
    bl_idname = "textify.save_copy"
    bl_label = "Save Copy"
    bl_description = "Save a copy of the current script"

    filepath: StringProperty(subtype="FILE_PATH")
    filter_glob: StringProperty(
        default="*.py;*.txt;*.glsl;*.osl;*.lua;*.xml;*.json", options={'HIDDEN'})

    def execute(self, context):
        text = getattr(context.space_data, 'text', None)
        if not text:
            self.report({'ERROR'}, "No text to save")
            return {'CANCELLED'}

        if not self.filepath:
            return {'CANCELLED'}

        try:
            # Add .py extension if no extension exists
            filepath = Path(self.filepath)
            if not filepath.suffix:
                filepath = filepath.with_suffix('.py')
                self.filepath = str(filepath)

            # Save using file.write()
            with open(self.filepath, 'w', encoding='utf-8') as f:
                f.write(text.as_string())

            recent_manager.add_file(self.filepath)
            self.report({'INFO'}, f"Copy saved to: {filepath.name}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to save copy: {e}")
            return {'CANCELLED'}

    def invoke(self, context, event):
        text = getattr(context.space_data, 'text', None)
        if text and text.name:
            self.filepath = text.name
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class TEXTIFY_OT_recent_files_actions(bpy.types.Operator):
    bl_idname = "textify.recent_files_actions"
    bl_label = "Recent Files Actions"
    bl_description = "Add, remove, open, reorder, or refresh recent files"

    action: EnumProperty(
        items=[
            ('ADD', 'Add', 'Add current script to recent files'),
            ('REMOVE', 'Remove', 'Remove selected file from recent files'),
            ('OPEN', 'Open', 'Open selected file in text editor'),
            ('MOVE_UP', 'Move Up', 'Move selected file up'),
            ('MOVE_DOWN', 'Move Down', 'Move selected file down'),
            ('REFRESH', 'Refresh', 'Refresh the UI list of recent files'),
        ]
    )

    def execute(self, context):
        props = context.window_manager.recent_files_props
        index = props.active_index
        recent_files = recent_manager.get_all_files()

        if self.action == 'ADD':
            text = getattr(context.space_data, 'text', None)
            if not text or not text.filepath:
                self.report({'ERROR'}, "No file to add or file not saved")
                return {'CANCELLED'}
            if not recent_manager.file_exists_in_list(text.filepath):
                recent_manager.add_file(text.filepath, reorder=True)
                self.report({'INFO'}, "File added to recent list")

        elif self.action == 'REMOVE':
            if 0 <= index < len(recent_files):
                recent_manager.remove_file(recent_files[index])
                props.active_index = max(0, index - 1)
                self.report({'INFO'}, "File removed")
            else:
                self.report({'ERROR'}, "No file selected")

        elif self.action == 'OPEN':
            if 0 <= index < len(recent_files):
                filepath = Path(recent_files[index])
                if filepath.exists():
                    # Check if file is already open
                    for text in bpy.data.texts:
                        if Path(text.filepath).resolve() == filepath.resolve():
                            context.space_data.text = text  # Switch to already opened text block
                            return {'FINISHED'}

                    # Not open yet — open it
                    try:
                        bpy.ops.text.open(filepath=str(filepath))
                        recent_manager.add_file(filepath, reorder=True)
                        return {'FINISHED'}
                    except Exception as e:
                        self.report({'ERROR'}, f"Failed to open file: {e}")
                        return {'CANCELLED'}
                else:
                    self.report({'ERROR'}, "File does not exist")
            else:
                self.report({'ERROR'}, "No file selected")

        elif self.action in {'MOVE_UP', 'MOVE_DOWN'}:
            if 0 <= index < len(recent_files):
                direction = -1 if self.action == 'MOVE_UP' else 1
                target_index = index + direction
                if 0 <= target_index < len(recent_files):
                    recent_manager.swap_files(index, target_index)
                    props.active_index = target_index
            else:
                self.report({'ERROR'}, "No file selected")

        elif self.action == 'REFRESH':
            sync_ui_list(context)
            self.report({'INFO'}, "UI list refreshed")

        return {'FINISHED'}


class TEXTIFY_OT_clear_recent_files(Operator):
    bl_idname = "textify.clear_recent"
    bl_label = "Clear Recent Files"
    bl_description = "Clear recent files"

    mode: EnumProperty(
        name="Remove",
        description="Choose which recent files to clear",
        items=[
            ('ALL', "All", "Clear all recent files"),
            ('MISSING', "Missing Only", "Remove only missing (not found) recent files")
        ],
        default='ALL'
    )

    def invoke(self, context, event):
        # Open a popup to let user select the clear mode
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        if self.mode == 'ALL':
            recent_manager.clear_recent_files()
            context.window_manager.recent_files_props.active_index = 0
            self.report({'INFO'}, "All recent files cleared")
        elif self.mode == 'MISSING':
            recent_manager.remove_missing_files()
            self.report({'INFO'}, "Missing recent files removed")
        else:
            self.report({'WARNING'}, "Invalid mode selected")
            return {'CANCELLED'}

        return {'FINISHED'}


class TEXTIFY_MT_open_recent(Menu):
    bl_idname = "TEXTIFY_MT_open_recent"
    bl_label = "Open Recent"
    bl_options = {'SEARCH_ON_KEY_PRESS'}

    def draw(self, context):
        layout = self.layout
        prefs = get_addon_prefs(context)
        valid_files, invalid_files = recent_manager.get_recent_files()

        if valid_files:
            for item in valid_files:
                path = Path(item['filepath'])

                if prefs.show_folder_name and path.name == "__init__.py":
                    # Use parent folder's name, replace spaces with underscores, append .py
                    folder_name = path.parent.name.replace(" ", "_")
                    display_name = f"{folder_name}.py" if folder_name else "__init__.py"
                else:
                    display_name = path.name

                op = layout.operator(
                    "textify.open_file",
                    text=display_name,
                    icon='WORDWRAP_ON'
                )
                op.filepath = str(path)

            layout.separator()
            layout.operator("textify.clear_recent",
                            text="Clear Recent Files                        ", icon='TRASH')
        else:
            layout.label(text="No recent files")


def textify_menu(self, context):
    layout = self.layout
    st = context.space_data
    text = st.text

    # New and Open
    layout.operator("text.new", text="New", icon='FILE_NEW')
    layout.operator("textify.open",
                    text="Open...", icon='FILE_FOLDER')
    layout.menu("TEXTIFY_MT_open_recent")

    if text:
        layout.separator()

        # Reload
        row = layout.row()
        row.operator("text.reload")
        row.enabled = not text.is_in_memory

        # External edit
        row = layout.row()
        row.operator("text.jump_to_file_at_point", text="Edit Externally")
        row.enabled = (not text.is_in_memory and
                       context.preferences.filepaths.text_editor != "")

        layout.separator()

        # Save operations
        layout.operator("textify.save", icon='FILE_TICK')
        layout.operator("textify.save_as", text="Save As...           ")
        layout.operator("textify.save_copy", text="Save Copy...")

        if text.filepath:
            layout.separator()
            layout.operator("text.make_internal")

        layout.separator()
        layout.prop(text, "use_module")
        layout.prop(st, "use_live_edit")

        layout.separator()
        layout.operator("text.run_script")


def textify_header(self, context):
    layout = self.layout
    wm = context.window_manager
    st = context.space_data
    text = st.text
    is_syntax_highlight_supported = st.is_syntax_highlight_supported()
    prefs = get_addon_prefs(context)

    layout.template_header()

    # Draw collapsible menus
    from bl_ui.space_text import TEXT_MT_editor_menus
    TEXT_MT_editor_menus.draw_collapsible(context, layout)

    layout.separator_spacer()

    # Modified file indicator
    if text and text.is_modified:
        row = layout.row(align=True)
        row.alert = True
        row.operator("text.resolve_conflict", text="", icon='QUESTION')

    # File operations
    row = layout.row(align=True)
    if text:
        row.template_ID(st, "text", new="text.new",
                        unlink="text.unlink", open="textify.open")

        if text.name.endswith((".osl", ".oso")):
            row.operator("node.shader_script_update",
                         text="", icon='FILE_REFRESH')
        else:
            play_row = layout.row()
            play_row.active = st.is_syntax_highlight_supported()
            play_row.operator("text.run_script", text="", icon='PLAY')
    else:
        row.template_ID(st, "text", new="text.new",
                        unlink="text.unlink", open="textify.open")

    layout.separator_spacer()

    # Display options
    row = layout.row(align=True)
    row.prop(st, "show_line_numbers", text="")
    row.prop(st, "show_word_wrap", text="")

    syntax = row.row(align=True)
    syntax.active = is_syntax_highlight_supported
    syntax.prop(st, "show_syntax_highlight", text="")

    # Jump to line tool
    if hasattr(wm, "jump_to_line_props") and getattr(prefs, "enable_jump_to_line", True):
        jump_row = layout.row(align=True)
        jump_row.scale_x = 0.9
        jump_row.prop(wm.jump_to_line_props,
                      "line_number", text="Line")


class TEXTIFY_PT_open_recent(bpy.types.Panel):
    bl_label = "Open Recent"
    bl_idname = "TEXTIFY_PT_open_recent"
    bl_space_type = 'TEXT_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Text"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        prefs = get_addon_prefs(context)
        return (
            getattr(prefs, "show_open_recent_panel", False) and
            context.space_data and
            context.space_data.type == 'TEXT_EDITOR' and
            context.space_data.text is not None
        )

    def draw(self, context):
        layout = self.layout
        text = context.space_data.text
        props = context.window_manager.recent_files_props
        prefs = get_addon_prefs(context)

        # Ensure recent files are loaded
        recent_files = recent_manager.get_all_files()

        if recent_files:
            # UI List
            row = layout.row()
            row.template_list("TEXTIFY_UL_recent_files", "",
                              props, "recent_files",
                              props, "active_index", rows=10)

            # Action buttons
            col = row.column(align=True)
            if text and not any(item.filepath == text.filepath for item in props.recent_files) and not text.is_in_memory:
                sub = col.column(align=True)
                sub.operator("textify.recent_files_actions",
                             icon='ADD', text="").action = 'ADD'
            else:
                sub = col.column(align=True)
                sub.operator("textify.recent_files_actions",
                             icon='ADD', text="").action = 'ADD'
                sub.enabled = False

            col.operator("textify.recent_files_actions", text="",
                         icon='REMOVE').action = 'REMOVE'

            col.separator()
            col.operator("textify.recent_files_actions", text="",
                         icon='TRIA_UP').action = 'MOVE_UP'
            col.operator("textify.recent_files_actions", text="",
                         icon='TRIA_DOWN').action = 'MOVE_DOWN'

            col.separator()
            col.operator("textify.recent_files_actions", text="",
                         icon='FILE_REFRESH').action = 'REFRESH'

            col.separator()
            col.operator("textify.clear_recent",
                         text="", icon='TRASH')

            col.separator()
            col.prop(prefs, "show_folder_name", text="", icon='FILTER')

            # layout.separator()
            layout.operator("textify.recent_files_actions",
                            text="Open", icon='FILE_FOLDER').action = 'OPEN'
        else:
            layout.label(text="No recent files")
            layout.operator("textify.recent_files_actions",
                            text="Add Current", icon='ADD').action = 'ADD'


# Registration
classes = (
    RecentFileItem,
    TEXTIFY_PG_Properties,

    TEXTIFY_UL_recent_files,

    TEXTIFY_OT_open_recent_file,
    TEXTIFY_OT_open_file_browser,
    TEXTIFY_OT_save,
    TEXTIFY_OT_save_as,
    TEXTIFY_OT_save_copy,
    TEXTIFY_OT_recent_files_actions,

    TEXTIFY_OT_clear_recent_files,
    TEXTIFY_MT_open_recent,
    TEXTIFY_PT_open_recent,
)


def register():
    try:
        # Register classes
        for cls in classes:
            bpy.utils.register_class(cls)

        # Register properties
        bpy.types.WindowManager.recent_files_props = PointerProperty(
            type=TEXTIFY_PG_Properties)

        # Replace original draw methods
        bpy.types.TEXT_HT_header.draw = textify_header
        bpy.types.TEXT_MT_text.draw = textify_menu

        # Add load handler
        if load_post_handler not in bpy.app.handlers.load_post:
            bpy.app.handlers.load_post.append(load_post_handler)

    except Exception as e:
        print(f"[Register] Error: {e}")


def unregister():
    try:

        # Remove handler
        if load_post_handler in bpy.app.handlers.load_post:
            bpy.app.handlers.load_post.remove(load_post_handler)

        # Unregister properties
        del bpy.types.WindowManager.recent_files_props

        # Unregister classes
        for cls in reversed(classes):
            bpy.utils.unregister_class(cls)
    except Exception as e:
        print(f"[Unregister] Error: {e}")

    # Force reload the entire bl_ui.space_text module
    import bl_ui.space_text
    import importlib
    importlib.reload(bl_ui.space_text)
