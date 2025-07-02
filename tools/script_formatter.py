import bpy
import subprocess
import sys


def get_addon_prefs(context):
    for addon_id in context.preferences.addons.keys():
        if 'textify' in addon_id.lower():
            return context.preferences.addons[addon_id].preferences
    return None


def install_modules(modules):
    try:
        subprocess.run(
            [sys.executable, "-m", "ensurepip"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        subprocess.run(
            [sys.executable, "-m", "pip", "install",
                "--upgrade", "pip", "--no-warn-script-location"],
            check=True
        )
        subprocess.run(
            [sys.executable, "-m", "pip", "install",
                "--no-warn-script-location", *modules],
            check=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"[Installer Error] {e}")
        return False


class TEXT_OT_install_formatter_deps(bpy.types.Operator):
    bl_idname = "text.install_formatter_deps"
    bl_label = "Install Formatter Dependencies"
    bl_description = "Install selected formatter dependencies using pip"

    install_autopep8: bpy.props.BoolProperty(name="autopep8", default=True)
    install_pycodestyle: bpy.props.BoolProperty(
        name="pycodestyle", default=True)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=300)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Select modules to install:")
        layout.prop(self, "install_autopep8")
        layout.prop(self, "install_pycodestyle")

    def execute(self, context):
        modules = []
        if self.install_autopep8:
            modules.append("autopep8")
        if self.install_pycodestyle:
            modules.append("pycodestyle")

        if not modules:
            self.report({'WARNING'}, "No modules selected.")
            return {'CANCELLED'}

        success = install_modules(modules)
        if success:
            self.report({'INFO'}, f"Installed: {', '.join(modules)}")
        else:
            self.report({'ERROR'}, "Module installation failed.")
        return {'FINISHED'}


class TEXTIFY_OT_format_autopep8(bpy.types.Operator):
    """Format current script using autopep8 (ignores E402)"""
    bl_idname = "textify.format_autopep8"
    bl_label = "Format with autopep8"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        text = context.space_data.text
        if not text:
            self.report({'WARNING'}, "No text block found in the Text Editor.")
            return {'CANCELLED'}

        try:
            import autopep8
        except ImportError:
            self.report(
                {'ERROR'}, "autopep8 is not installed. Use the install operator in preferences.")
            return {'CANCELLED'}

        source_code = "\n".join(line.body for line in text.lines)

        try:
            # Ignore E402 (imports not at top of file)
            formatted_code = autopep8.fix_code(
                source_code, options={'ignore': ['E402']})
        except Exception as e:
            self.report({'ERROR'}, f"Formatting failed: {e}")
            return {'CANCELLED'}

        text.clear()
        for line in formatted_code.splitlines():
            text.write(line + "\n")

        self.report({'INFO'}, "Script formatted successfully.")
        return {'FINISHED'}


def menu_func(self, context):
    if getattr(get_addon_prefs(context), "enable_script_formatter", False):
        self.layout.separator()
        self.layout.operator(
            TEXTIFY_OT_format_autopep8.bl_idname, icon='FILE_SCRIPT')


classes = (
    TEXT_OT_install_formatter_deps,
    TEXTIFY_OT_format_autopep8,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TEXT_MT_format.append(menu_func)


def unregister():
    bpy.types.TEXT_MT_format.remove(menu_func)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
