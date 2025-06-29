import bpy


def update_line_number(self, context):
    text_editor = context.space_data.text
    props = context.window_manager.jump_to_line_props
    if text_editor is not None:
        lines = text_editor.as_string().split('\n')

        line_number = props.line_number
        if line_number > 0:
            # Calculate the maximum line number based on the
            # actual number of lines in the script
            max_line_number = len(lines)
            if line_number > max_line_number:
                line_number = max_line_number
                props.line_number = line_number

            bpy.ops.text.jump(line=line_number)


class JUMP_TO_LINE_PG_properties(bpy.types.PropertyGroup):
    recent_list: bpy.props.CollectionProperty(type=bpy.types.PropertyGroup)
    recent_list_index: bpy.props.IntProperty(name="Recent list index")
    line_number: bpy.props.IntProperty(
        name="Line Number",
        min=1,
        update=update_line_number
    )


def register():
    bpy.utils.register_class(JUMP_TO_LINE_PG_properties)
    bpy.types.WindowManager.jump_to_line_props = bpy.props.PointerProperty(
        type=JUMP_TO_LINE_PG_properties)


def unregister():
    bpy.utils.unregister_class(JUMP_TO_LINE_PG_properties)
    del bpy.types.WindowManager.jump_to_line_props

