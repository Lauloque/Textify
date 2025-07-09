import bpy


def get_addon_prefs(context):
    for addon_id in context.preferences.addons.keys():
        if 'textify' in addon_id.lower():
            return context.preferences.addons[addon_id].preferences
    return None


def draw_character_count(self, context):
    layout = self.layout
    prefs = get_addon_prefs(context)

    if not getattr(prefs, "enable_character_count", False):
        return

    layout.separator_spacer()

    text = context.space_data.text
    if not text:
        return

    total_characters = sum(len(line.body) for line in text.lines)
    selection_active = text.current_line_index != text.select_end_line_index or \
        text.current_character != text.select_end_character

    if selection_active:
        start_line, end_line = sorted(
            (text.current_line_index, text.select_end_line_index))
        start_char, end_char = sorted(
            (text.current_character, text.select_end_character))

        if start_line == end_line:
            selected_characters = abs(end_char - start_char)
        else:
            selected_characters = (
                len(text.lines[start_line].body[start_char:]) +
                sum(len(line.body) for line in text.lines[start_line + 1:end_line]) +
                len(text.lines[end_line].body[:end_char])
            )

        cursor_line = text.select_end_line_index + 1
        cursor_col = text.select_end_character + 1
        layout.label(text=f"Ln {cursor_line}, Col {cursor_col}")
        layout.separator(type="LINE")
        layout.label(
            text=f"{selected_characters} of {total_characters} characters")
    else:
        cursor_line = text.current_line_index + 1
        cursor_col = text.current_character + 1
        layout.label(text=f"Ln {cursor_line}, Col {cursor_col}")
        layout.separator(type="LINE")
        layout.label(text=f"{total_characters} characters")


def register():
    bpy.types.TEXT_HT_footer.append(draw_character_count)


def unregister():
    bpy.types.TEXT_HT_footer.remove(draw_character_count)
