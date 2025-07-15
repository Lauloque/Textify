import bpy


def get_texts():
    return [text for text in bpy.data.texts if text.name]


def cycle_text_forward():
    texts = get_texts()
    space = bpy.context.space_data
    if not texts or not space or not space.text:
        return

    current = space.text
    index = texts.index(current)
    new_index = (index + 1) % len(texts)
    space.text = texts[new_index]


class TEXTIFY_OT_cycle_scripts(bpy.types.Operator):
    bl_idname = "textify.cycle_scripts"
    bl_label = "Cycle Scripts Forward"
    bl_description = "Cycle forward through open text blocks"

    @classmethod
    def poll(cls, context):
        return (
            context.space_data and
            context.space_data.type == 'TEXT_EDITOR' and
            context.space_data.text is not None
        )

    def execute(self, context):
        cycle_text_forward()
        return {'FINISHED'}


def register():
    bpy.utils.register_class(TEXTIFY_OT_cycle_scripts)


def unregister():
    bpy.utils.unregister_class(TEXTIFY_OT_cycle_scripts)
