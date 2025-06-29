import bpy
import platform
import subprocess

from pathlib import Path


def get_addon_prefs(context):
    for addon_id in context.preferences.addons.keys():
        if 'textify' in addon_id.lower():
            return context.preferences.addons[addon_id].preferences
    return None


class TEXT_OT_reveal_in_explorer(bpy.types.Operator):
    bl_idname = "text.reveal_in_explorer"
    bl_label = "Reveal In Explorer"
    bl_description = "Open the script's folder in the system file browser"

    def execute(self, context):
        text = context.space_data.text
        if not text or not text.filepath:
            self.report({'WARNING'}, "No saved file to reveal")
            return {'CANCELLED'}

        filepath = bpy.path.abspath(text.filepath)
        system = platform.system()

        try:
            if system == "Windows":
                filepath_win = str(filepath)
                subprocess.run(["explorer", f'/select,{filepath_win}'], check=True)
            elif system == "Darwin":
                subprocess.run(['open', '-R', filepath], check=True)
            elif system == "Linux":
                folder = str(Path(filepath).parent)
                subprocess.run(['xdg-open', folder], check=True)
            else:
                self.report({'ERROR'}, f"Unsupported OS: {system}")
                return {'CANCELLED'}

            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"System open failed: {e}. Falling back to wm.path_open.")
            try:
                bpy.ops.wm.path_open(filepath=str(Path(filepath).parent))
                return {'FINISHED'}
            except Exception as fallback_error:
                self.report({'ERROR'}, f"Fallback also failed: {fallback_error}")
                return {'CANCELLED'}


def draw_footer_menu(self, context):
    layout = self.layout
    text = context.space_data.text
    prefs = get_addon_prefs(context)

    if text and text.filepath and prefs.enable_open_script_folder:
        if prefs.enable_character_count:
            layout.separator(type='LINE')
        else:
            layout.separator_spacer()

        layout.operator("text.reveal_in_explorer", text="",
                        icon='FILE_FOLDER', emboss=False)


def register():
    bpy.utils.register_class(TEXT_OT_reveal_in_explorer)
    bpy.types.TEXT_HT_footer.append(draw_footer_menu)


def unregister():
    bpy.types.TEXT_HT_footer.remove(draw_footer_menu)
    bpy.utils.unregister_class(TEXT_OT_reveal_in_explorer)
