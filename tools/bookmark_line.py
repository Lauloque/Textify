import bpy
from bpy.props import StringProperty, EnumProperty, IntProperty, CollectionProperty
from bpy.types import PropertyGroup, Operator, Panel, UIList, Menu


# -------------------------------------------------------------
# Helpers
# -------------------------------------------------------------


def get_addon_prefs(context):
    """
    Get the addon preferences by searching for the textify addon.
    Returns the preferences object or None if not found.
    """
    for addon_id in context.preferences.addons.keys():
        if 'textify' in addon_id.lower():
            return context.preferences.addons[addon_id].preferences
    return None


def get_active_text():
    return getattr(bpy.context.space_data, "text", None)


def bookmark_jump(self, context):
    text = get_active_text()
    if not text:
        return
    settings = text.bookmark_settings
    text = context.space_data.text

    if text and 0 <= settings.bookmark_list_index < len(settings.bookmark_items):
        item = settings.bookmark_items[settings.bookmark_list_index]
        if item.line_index < len(text.lines):
            bpy.ops.text.jump(line=item.line_index + 1)


# -------------------------------------------------------------
# Properties
# -------------------------------------------------------------


class BookmarkItem(PropertyGroup):
    line_index: IntProperty()
    line_content: StringProperty()


class BookmarkSettings(PropertyGroup):
    bookmark_items: CollectionProperty(type=BookmarkItem)
    bookmark_list_index: IntProperty(default=0, update=bookmark_jump)


# -------------------------------------------------------------
# Operator
# -------------------------------------------------------------


class BOOKMARK_LINE_OT_manage(Operator):
    bl_idname = "bookmark_line.manage"
    bl_label = "Manage Bookmark"
    bl_options = {'REGISTER', 'UNDO'}

    action: EnumProperty(
        items=[
            ('ADD', "Add", "Add current line as bookmark"),
            ('REMOVE', "Remove", "Remove selected bookmark"),
            ('MOVE_UP', "Move Up", "Move bookmark up"),
            ('MOVE_DOWN', "Move Down", "Move bookmark down"),
            ('REFRESH', "Refresh", "Refresh saved bookmarks"),
            ('SORT', "Sort", "Sort bookmarks by line number")
        ],
        name="Action",
        default='ADD'
    )

    index: IntProperty(default=-1)

    @classmethod
    def poll(cls, context):
        prefs = get_addon_prefs(context)
        return (
            getattr(prefs, "enable_bookmark_line", False) and
            context.space_data and
            context.space_data.type == 'TEXT_EDITOR' and
            context.space_data.text is not None
        )

    def execute(self, context):
        text = get_active_text()

        if not text:
            self.report({'WARNING'}, "No active text block")
            return {'CANCELLED'}

        settings = text.bookmark_settings

        if self.action == 'ADD':
            if text.current_line:
                line_index = text.current_line_index
                content = text.current_line.body.strip()
                already_bookmarked = any(
                    b.line_index == line_index for b in settings.bookmark_items)
                if not already_bookmarked:
                    item = settings.bookmark_items.add()
                    item.line_index = line_index
                    item.line_content = content
                    settings.bookmark_list_index = len(
                        settings.bookmark_items) - 1

        elif self.action == 'REMOVE' and self.index >= 0 and self.index < len(settings.bookmark_items):
            settings.bookmark_items.remove(self.index)
            settings.bookmark_list_index = max(0, self.index - 1)

        elif self.action == 'MOVE_UP':
            idx = settings.bookmark_list_index
            if idx > 0:
                settings.bookmark_items.move(idx, idx - 1)
                settings.bookmark_list_index -= 1

        elif self.action == 'MOVE_DOWN':
            idx = settings.bookmark_list_index
            if idx < len(settings.bookmark_items) - 1:
                settings.bookmark_items.move(idx, idx + 1)
                settings.bookmark_list_index += 1

        elif self.action == 'REFRESH':
            current_lines = [line.body.strip() for line in text.lines]
            updated_items = []

            for item in settings.bookmark_items:
                old_index = item.line_index
                target_content = item.line_content

                # Direct match at old index
                if old_index < len(current_lines) and current_lines[old_index] == target_content:
                    updated_items.append((old_index, target_content))
                    continue

                # Fallback: search nearby for the same content
                found_index = -1
                search_range = range(max(0, old_index - 5),
                                     min(len(current_lines), old_index + 6))
                for i in search_range:
                    if current_lines[i] == target_content:
                        found_index = i
                        break

                if found_index != -1:
                    updated_items.append((found_index, target_content))

            # Only update if changed
            if len(updated_items) != len(settings.bookmark_items) or any(
                b.line_index != new[0] or b.line_content != new[1]
                for b, new in zip(settings.bookmark_items, updated_items)
            ):
                settings.bookmark_items.clear()
                for line_index, line_content in updated_items:
                    new_item = settings.bookmark_items.add()
                    new_item.line_index = line_index
                    new_item.line_content = line_content

        elif self.action == 'SORT':
            text_lines = [line.body.strip() for line in text.lines]
            updated_items = []

            for b in settings.bookmark_items:
                try:
                    new_index = text_lines.index(b.line_content)
                    updated_items.append((new_index, b.line_content))
                except ValueError:
                    continue  # Skip missing lines

            updated_items.sort(key=lambda pair: pair[0])

            # Only update if sorting changes the order
            existing = [(b.line_index, b.line_content)
                        for b in settings.bookmark_items]
            if existing != updated_items:
                settings.bookmark_items.clear()
                for line_index, line_content in updated_items:
                    new_item = settings.bookmark_items.add()
                    new_item.line_index = line_index
                    new_item.line_content = line_content

        return {'FINISHED'}


# -------------------------------------------------------------
# UI List
# -------------------------------------------------------------


class BOOKMARK_LINE_UL_bookmark_list(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.label(text=f"{item.line_index + 1}: {item.line_content[:80]}")


# -------------------------------------------------------------
# Draw Function
# -------------------------------------------------------------


def draw_bookmark_ui(layout):
    text = get_active_text()
    settings = text.bookmark_settings
    if not text:
        layout.label(text="No active text block", icon='ERROR')
        return

    row = layout.row()
    if text.current_line:
        current_line = text.current_line.body.strip()
        row.label(text=current_line if current_line else "(Empty Line)",
                  icon='INFO' if not current_line else 'NONE')

    if len(settings.bookmark_items) > 0:
        row = layout.row()
        row.template_list("BOOKMARK_LINE_UL_bookmark_list", "", settings,
                          "bookmark_items", settings, "bookmark_list_index", rows=6)

    col = row.column(align=True)
    col.operator("bookmark_line.manage", text="", icon='ADD').action = 'ADD'

    if len(settings.bookmark_items) > 0:
        op = col.operator("bookmark_line.manage", text="", icon='REMOVE')
        op.action = 'REMOVE'
        op.index = settings.bookmark_list_index

        col.separator()
        col.operator("bookmark_line.manage", text="",
                     icon='TRIA_UP').action = 'MOVE_UP'
        col.operator("bookmark_line.manage", text="",
                     icon='TRIA_DOWN').action = 'MOVE_DOWN'

        col.separator()
        col.operator("bookmark_line.manage", text="",
                     icon='FILE_REFRESH').action = 'REFRESH'

        col.separator()
        col.operator("bookmark_line.manage",
                     text="", icon='SORTSIZE').action = 'SORT'


class BOOKMARK_LINE_OT_popup(Operator):
    bl_idname = "bookmark_line.popup"
    bl_label = "Bookmark Manager"
    bl_description = "Manage line bookmarks"

    @classmethod
    def poll(cls, context):
        prefs = get_addon_prefs(context)
        return (
            getattr(prefs, "enable_bookmark_line", False) and
            context.space_data and
            context.space_data.type == 'TEXT_EDITOR' and
            context.space_data.text is not None
        )

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        draw_bookmark_ui(self.layout)


class BOOKMARK_LINE_PT_Panel(Panel):
    bl_label = "Manage Bookmarks"
    bl_idname = "BOOKMARK_LINE_PT_Panel"
    bl_space_type = 'TEXT_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Bookmark Line"

    @classmethod
    def poll(cls, context):
        prefs = get_addon_prefs(context)
        return (
            getattr(prefs, "enable_bookmark_line", False) and
            getattr(prefs, "show_bookmark_line_panel", False) and
            context.space_data and
            context.space_data.type == 'TEXT_EDITOR' and
            context.space_data.text is not None
        )

    def draw(self, context):
        draw_bookmark_ui(self.layout)


# -------------------------------------------------------------
# Registration
# -------------------------------------------------------------


classes = (
    BookmarkItem,
    BookmarkSettings,
    BOOKMARK_LINE_OT_manage,
    BOOKMARK_LINE_UL_bookmark_list,
    BOOKMARK_LINE_OT_popup,
    BOOKMARK_LINE_PT_Panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Text.bookmark_settings = bpy.props.PointerProperty(
        type=BookmarkSettings)


def unregister():
    del bpy.types.Text.bookmark_settings

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
