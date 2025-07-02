import bpy
import re


def get_addon_prefs(context):
    for addon_id in context.preferences.addons.keys():
        if 'textify' in addon_id.lower():
            return context.preferences.addons[addon_id].preferences
    return None


def to_snake_case(text):
    text = re.sub(r'[\s\-]+', '_', text)
    text = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', text)
    return text.lower()


def to_camel_case(text):
    parts = re.split(r'[\s\-_]+', text)
    return parts[0].lower() + ''.join(word.capitalize() for word in parts[1:])


class TEXTIFY_OT_convert_case(bpy.types.Operator):
    bl_idname = "textify.change_case"
    bl_label = "Convert Case"
    bl_description = "Convert the case of selected text"
    bl_options = {'REGISTER', 'UNDO'}

    case_type: bpy.props.StringProperty()

    @classmethod
    def poll(cls, context):
        prefs = get_addon_prefs(context)
        return (
            getattr(prefs, "enable_case_convert", False) and
            context.space_data and
            context.space_data.type == 'TEXT_EDITOR' and
            context.space_data.text is not None
        )

    def execute(self, context):
        text = context.space_data.text
        if not text:
            self.report({'WARNING'}, "No text block open")
            return {'CANCELLED'}

        line = text.current_line
        sel_line = text.select_end_line

        if line == sel_line and text.current_character == text.select_end_character:
            bpy.ops.text.select_word()
            line = text.current_line
            sel_line = text.select_end_line

        if line != sel_line:
            self.report({'WARNING'}, "Only single-line selection supported")
            return {'CANCELLED'}

        start = min(text.current_character, text.select_end_character)
        end = max(text.current_character, text.select_end_character)

        if start == end:
            self.report({'WARNING'}, "No text selected")
            return {'CANCELLED'}

        original = line.body[start:end]

        if self.case_type == 'UPPERCASE':
            converted = original.upper()
        elif self.case_type == 'LOWERCASE':
            converted = original.lower()
        elif self.case_type == 'TITLECASE':
            converted = original.title()
        elif self.case_type == 'CAPITALIZE':
            converted = original.capitalize()
        elif self.case_type == 'SNAKECASE':
            converted = to_snake_case(original)
        elif self.case_type == 'CAMELCASE':
            converted = to_camel_case(original)
        else:
            self.report({'WARNING'}, "Invalid case type")
            return {'CANCELLED'}

        line.body = line.body[:start] + converted + line.body[end:]
        return {'FINISHED'}


class TEXTIFY_MT_change_case_menu(bpy.types.Menu):
    bl_label = "Convert Case to"
    bl_idname = "TEXTIFY_MT_change_case_menu"

    def draw(self, context):
        layout = self.layout
        space = context.space_data
        text = getattr(space, "text", None)

        cases = [
            ('UPPERCASE', "UPPER CASE"),
            ('LOWERCASE', "lower case"),
            ('TITLECASE', "Title Case"),
            ('CAPITALIZE', "Capitalize"),
            ('SNAKECASE', "snake_case"),
            ('CAMELCASE', "CamelCase"),
        ]
        for case_id, label in cases:
            layout.operator(TEXTIFY_OT_convert_case.bl_idname,
                            text=label).case_type = case_id


def menu_func(self, context):
    prefs = get_addon_prefs(context)
    if getattr(prefs, "enable_case_convert", False):
        self.layout.separator()
        self.layout.menu(TEXTIFY_MT_change_case_menu.bl_idname)


classes = (
    TEXTIFY_OT_convert_case,
    TEXTIFY_MT_change_case_menu,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TEXT_MT_format.append(menu_func)
    bpy.types.TEXT_MT_context_menu.append(menu_func)


def unregister():
    bpy.types.TEXT_MT_context_menu.remove(menu_func)
    bpy.types.TEXT_MT_format.remove(menu_func)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
