import bpy


def update_line_number(self, context):
    text = context.space_data.text
    props = context.window_manager.jump_to_line_props

    if text:
        max_line_number = len(text.lines)
        line_number = props.line_number

        if line_number > max_line_number:
            line_number = max_line_number
            props.line_number = line_number

        bpy.ops.text.jump(line=line_number)


class JUMP_TO_LINE_PG_properties(bpy.types.PropertyGroup):
    line_number: bpy.props.IntProperty(
        name="Line Number",
        min=1,
        update=update_line_number
    )


def register():
    bpy.utils.register_class(JUMP_TO_LINE_PG_properties)
    bpy.types.WindowManager.jump_to_line_props = bpy.props.PointerProperty(
        type=JUMP_TO_LINE_PG_properties
    )


def unregister():
    del bpy.types.WindowManager.jump_to_line_props
    bpy.utils.unregister_class(JUMP_TO_LINE_PG_properties)
