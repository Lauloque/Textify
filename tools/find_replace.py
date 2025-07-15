import bpy
from bpy.app.translations import contexts as i18n_contexts
from ..textify_icons import get_icon


# ------------------------------------------------------------------------
# Utility Functions
# ------------------------------------------------------------------------


def get_addon_prefs(context):
    for addon_id in context.preferences.addons.keys():
        if 'textify' in addon_id.lower():
            return context.preferences.addons[addon_id].preferences
    return None


# ------------------------------------------------------------------------
# Property Group
# ------------------------------------------------------------------------


class FIND_REPLACE_PG_properties(bpy.types.PropertyGroup):
    def update_search(self, context):
        prefs = get_addon_prefs(context)
        if prefs is None or context.area is None or context.area.type != 'TEXT_EDITOR':
            return

        context.space_data.find_text = self.find_text
        context.space_data.replace_text = self.replace_text

        # Run search if the user allows automatic find on enter
        if prefs.enable_find_on_enter:
            bpy.ops.text.find()

    def update_realtime_search(self, context):
        if context.area and context.area.type == 'TEXT_EDITOR':
            context.space_data.find_text = self.find_text_live
            context.space_data.replace_text = self.replace_text_live

    def update_replace_search(self, context):
        if context.area and context.area.type == 'TEXT_EDITOR':
            context.space_data.find_text = self.find_text
            context.space_data.replace_text = self.replace_text

    def update_replace_realtime(self, context):
        if context.area and context.area.type == 'TEXT_EDITOR':
            context.space_data.find_text = self.find_text_live
            context.space_data.replace_text = self.replace_text_live

    find_text: bpy.props.StringProperty(
        name="Find Text",
        description="Text to search for with the find tool",
        update=update_search,
    )

    find_text_live: bpy.props.StringProperty(
        name="Find Text (Real-time)",
        description="Text to search for with real-time search enabled",
        update=update_realtime_search,
        options={'TEXTEDIT_UPDATE'}
    )

    replace_text: bpy.props.StringProperty(
        name="Replace Text",
        description="Text to replace selected text with using the replace tool",
        update=update_replace_search,
    )

    replace_text_live: bpy.props.StringProperty(
        name="Replace Text (Real-time)",
        description="Text to replace selected text with using the replace tool in real-time mode",
        update=update_replace_realtime,
        options={'TEXTEDIT_UPDATE'}
    )


# ------------------------------------------------------------------------
# Operator: Find Previous
# ------------------------------------------------------------------------


class TEXT_OT_find_previous(bpy.types.Operator):
    bl_idname = "text.find_previous"
    bl_label = "Find Previous"
    bl_description = "Find specified text"

    def execute(self, context):
        text_data = context.edit_text
        space_data = context.space_data

        if not text_data or not space_data.find_text:
            self.report({'INFO'}, "No search text specified")
            return {'CANCELLED'}

        find = space_data.find_text
        cursor_line = text_data.current_line_index
        cursor_character = text_data.current_character
        match_case = space_data.use_match_case
        lines_displayed = context.area.height // 16

        if self.search(text_data, find, cursor_line, cursor_character, match_case, lines_displayed, reverse=True):
            return {'FINISHED'}

        if self.search(text_data, find, len(text_data.lines) - 1, None, match_case, lines_displayed, reverse=True, limit=cursor_line):
            return {'FINISHED'}

        self.report({'INFO'}, f"Text not found: {find}")
        return {'FINISHED'}

    def search(self, text_data, find_text, start_line, start_char, match_case, lines_displayed, reverse=False, limit=None):
        if not match_case:
            find_text = find_text.lower()

        step = -1 if reverse else 1
        end = limit if limit is not None else (
            -1 if reverse else len(text_data.lines))

        for i in range(start_line, end, step):
            line = text_data.lines[i].body
            search_line = line if i != start_line or start_char is None else line[:start_char]
            haystack = search_line if match_case else search_line.lower()

            index = haystack.rfind(
                find_text) if reverse else haystack.find(find_text)
            if index != -1:
                self.select(text_data, i, index, len(
                    find_text), lines_displayed)
                return True
        return False

    def select(self, text_data, line_index, char_index, length, lines_displayed):
        text_data.current_line_index = line_index
        text_data.current_character = char_index + length
        text_data.select_set(line_index, char_index,
                             line_index, char_index + length)

        space_data = bpy.context.space_data
        if not (space_data.top <= line_index <= space_data.top + lines_displayed):
            space_data.top = max(0, line_index - lines_displayed // 2)


# ------------------------------------------------------------------------
# Operator: Find and Replace Popup
# ------------------------------------------------------------------------


class TEXT_OT_find_replace(bpy.types.Operator):
    bl_idname = "text.find_replace"
    bl_label = "Find & Replace"

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        st = context.space_data
        text = st.text
        wm_textify = context.window_manager.textify
        prefs = get_addon_prefs(context)

        if text:
            sel_start, sel_end = text.current_character, text.select_end_character
            if sel_start != sel_end:
                selected = text.current_line.body[min(
                    sel_start, sel_end):max(sel_start, sel_end)]

                # Set the appropriate properties based on realtime_search setting
                if prefs and prefs.realtime_search:
                    wm_textify.find_text_live = selected
                    wm_textify.replace_text_live = selected
                else:
                    wm_textify.find_text = selected
                    wm_textify.replace_text = selected

                bpy.ops.text.find_set_selected()
                bpy.ops.text.find_previous()
                bpy.ops.text.replace_set_selected()

        # Determine text length for popup width calculation
        if prefs and prefs.realtime_search:
            find_text_len = len(wm_textify.find_text_live)
            replace_text_len = len(wm_textify.replace_text_live)
        else:
            find_text_len = len(wm_textify.find_text)
            replace_text_len = len(wm_textify.replace_text)

        width = 430 if max(find_text_len, replace_text_len) > 54 else 360
        return context.window_manager.invoke_popup(self, width=width)

    def draw(self, context):
        layout = self.layout
        st = context.space_data
        wm_textify = context.window_manager.textify
        prefs = get_addon_prefs(context)

        row = layout.row(align=True)
        row.label(text="Find & Replace")
        if st.find_text:
            col = row.column(align=True)
            col.alignment = 'RIGHT'
            self.display_word_count(context, col, st.find_text, prefs)

        layout.separator(type="LINE")
        self.draw_settings(layout, st, prefs)
        self.draw_find_replace(layout, st, wm_textify, prefs)

    def draw_settings(self, layout, st, prefs):
        row = layout.row(align=True)
        row.prop(st, "use_match_case", text="Match Case", toggle=True)
        row.prop(st, "use_find_wrap", text="Wrap Around", toggle=True)
        row.prop(st, "use_find_all", text="All Data-Blocks", toggle=True)

        if getattr(prefs, "highlight_mode", "") != "SELECTION":
            row.separator()
            row.prop(prefs, "enable_highlight_occurrences", text="",
                     icon_value=get_icon("highlight"), toggle=True)

        layout.separator()

    def draw_find_replace(self, layout, st, wm_textify, prefs):
        text_data = bpy.context.edit_text
        total_count, current_count = self.count_occurrences(
            st.text, text_data, st.find_text, st.use_match_case
        )

        row = layout.row(align=True)
        row.scale_x = 1.1
        sub = row.row(align=True)

        if prefs.use_textify_find_replace:
            prop = wm_textify
        else:
            prop = st

        if getattr(prefs, "auto_activate_find", False) and not st.find_text:
            sub.activate_init = True

        # Use appropriate find_text property based on realtime_search setting
        if prefs and prefs.realtime_search and prefs.use_textify_find_replace:
            sub.prop(prop, "find_text_live", text="", icon='VIEWZOOM')
        else:
            sub.prop(prop, "find_text", text="", icon='VIEWZOOM')

        row.operator("text.find", text="", icon="SORT_ASC")
        row.operator("text.find_previous", text="", icon="SORT_DESC")

        row = layout.row(align=True)
        row.scale_x = 1.1

        # Use appropriate replace_text property based on realtime_search setting
        if prefs and prefs.realtime_search and prefs.use_textify_find_replace:
            row.prop(prop, "replace_text_live", text="", icon='DECORATE_OVERRIDE')
        else:
            row.prop(prop, "replace_text", text="", icon='DECORATE_OVERRIDE')
        row.operator("text.replace", text="", icon="ARROW_LEFTRIGHT")
        row.operator("text.replace", text="", icon="ANIM").all = True

    def display_word_count(self, context, col, find, prefs):
        total, current = self.count_occurrences(
            context.space_data.text, context.edit_text, find, context.space_data.use_match_case
        )
        label = "No matches found" if total == 0 else f"{current} of {total}"
        col.label(text=label)

    def count_occurrences(self, text, text_data, find, use_match_case):
        total = current = 0
        if not (text and text_data and find):
            return total, current

        search = find if use_match_case else find.lower()

        for i, line in enumerate(text_data.lines):
            line_body = line.body
            search_line = line_body if use_match_case else line_body.lower()
            matches = search_line.count(search)
            total += matches

            if i < text_data.current_line_index:
                current += matches
            elif i == text_data.current_line_index:
                end_char = min(text_data.select_end_character, len(line_body))
                current += search_line[:end_char].count(search)

        return total, current


# ------------------------------------------------------------------------
# Panel UI
# ------------------------------------------------------------------------


def textify_find_replace_draw(self, context):
    layout = self.layout
    st = context.space_data
    wm_textify = context.window_manager.textify
    prefs = get_addon_prefs(context)

    layout.active = bool(st.text)

    if prefs.use_textify_find_replace:
        prop = wm_textify
    else:
        prop = st

    col = layout.column()
    row = col.row(align=True)

    # Use appropriate find_text property based on realtime_search setting
    if prefs and prefs.realtime_search and prefs.use_textify_find_replace:
        row.prop(prop, "find_text_live", text="", icon='VIEWZOOM')
    else:
        row.prop(prop, "find_text", text="", icon='VIEWZOOM')

    row.operator("text.find_set_selected", text="", icon='EYEDROPPER')

    row = col.row(align=True)
    row.operator("text.find")
    row.operator("text.find_previous")

    layout.separator()
    col = layout.column()
    row = col.row(align=True)

    # Use appropriate replace_text property based on realtime_search setting
    if prefs and prefs.realtime_search and prefs.use_textify_find_replace:
        row.prop(prop, "replace_text_live", text="", icon='DECORATE_OVERRIDE')
    else:
        row.prop(prop, "replace_text", text="", icon='DECORATE_OVERRIDE')

    row.operator("text.replace_set_selected", text="", icon='EYEDROPPER')

    row = col.row(align=True)
    row.operator("text.replace")
    row.operator("text.replace", text="Replace All").all = True

    layout.separator()
    layout.use_property_split = True
    col = layout.column(heading="Search")
    col.active = bool(st.text)
    col.prop(st, "use_match_case", text="Match Case",
             text_ctxt=i18n_contexts.id_text)
    col.prop(st, "use_find_wrap", text="Wrap Around",
             text_ctxt=i18n_contexts.id_text)
    col.prop(st, "use_find_all", text="All Data-Blocks")


# ------------------------------------------------------------------------
# Menu Integration
# ------------------------------------------------------------------------


def draw_func(self, context):
    self.layout.separator()
    self.layout.operator("text.find_replace", text="Textify Find & Replace")


# ------------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------------


original_text_pt_find_draw = bpy.types.TEXT_PT_find.draw


classes = [
    FIND_REPLACE_PG_properties,
    TEXT_OT_find_previous,
    TEXT_OT_find_replace,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.TEXT_PT_find.draw = textify_find_replace_draw

    bpy.types.TEXT_MT_edit.append(draw_func)
    bpy.types.WindowManager.textify = bpy.props.PointerProperty(
        type=FIND_REPLACE_PG_properties)


def unregister():
    bpy.types.TEXT_MT_edit.remove(draw_func)
    del bpy.types.WindowManager.textify

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    bpy.types.TEXT_PT_find.draw = original_text_pt_find_draw
