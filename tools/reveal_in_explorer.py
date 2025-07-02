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
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return (
            context.space_data and
            context.space_data.text and
            context.space_data.text.filepath
        )

    def execute(self, context):
        script_path = Path(bpy.path.abspath(context.space_data.text.filepath))

        if not script_path.exists():
            self.report({'WARNING'}, "Please save the script first.")
            return {'CANCELLED'}

        script_folder = script_path.parent
        current_os = platform.system()

        try:
            if current_os == "Windows":
                subprocess.run(["explorer", "/select,", str(script_path)])
            elif current_os == "Darwin":
                subprocess.run(["open", "-R", str(script_path)])
            elif current_os == "Linux":
                subprocess.run(["xdg-open", str(script_folder)])
            else:
                self.report(
                    {'ERROR'}, f"Unsupported operating system: {current_os}")
                return {'CANCELLED'}
        except FileNotFoundError:
            self.report(
                {'ERROR'}, f"Could not find a file explorer command for {current_os}.")
            return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f"An error occurred: {e}")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Opened folder and selected: {script_path}")
        return {'FINISHED'}


def draw_footer_menu(self, context):
    layout = self.layout
    text = context.space_data.text
    prefs = get_addon_prefs(context)

    if text and text.filepath and getattr(prefs, "enable_open_script_folder", False):
        if getattr(prefs, "enable_character_count", False):
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
