import bpy
import zipfile
import tempfile
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, Iterator, List
import re
import ast


# -------------------------------------------------------------
#                    Constants & Config
# -------------------------------------------------------------

ADDON_MANIFEST_FILE = "blender_manifest.toml"
ADDON_INIT_FILE = "__init__.py"
SYSTEM_REPO_NAMES = {'system', 'built-in', 'blender'}

# Pre-compiled regex patterns for better performance
TOML_NAME_PATTERN = re.compile(r'name\s*=\s*["\']([^"\']+)["\']')
TOML_VERSION_PATTERN = re.compile(r'version\s*=\s*["\']([^"\']+)["\']')
BL_INFO_PATTERN = re.compile(
    r'bl_info\s*=\s*(\{(?:[^{}]|{[^}]*})*\})', re.DOTALL)
BL_INFO_NAME_PATTERN = re.compile(r'["\']name["\']\s*:\s*["\']([^"\']+)["\']')
BL_INFO_VERSION_PATTERN = re.compile(r'["\']version["\']\s*:\s*\(([^)]+)\)')


# -------------------------------------------------------------
#                    Data Classes & Utils
# -------------------------------------------------------------

class AddonInfo:
    """Immutable addon information container"""
    __slots__ = ('name', 'version', 'addon_type', 'root_path')

    def __init__(self, name: str = "Unknown Addon", version: str = "Unknown",
                 addon_type: str = "Addon", root_path: Optional[str] = None):
        self.name = name
        self.version = version
        self.addon_type = addon_type
        self.root_path = root_path

    @property
    def clean_name(self) -> str:
        """Get filesystem-safe name"""
        return self.name.lower().replace(" ", "_").replace("-", "_")

    def to_tuple(self) -> Tuple[str, str, str, Optional[str]]:
        """Convert to tuple for backward compatibility"""
        return (self.name, self.version, self.addon_type, self.root_path)


def get_addon_prefs(context) -> Optional[Any]:
    """Get addon preferences efficiently"""
    for addon_id in context.preferences.addons.keys():
        if 'textify' in addon_id.lower():
            return context.preferences.addons[addon_id].preferences
    return None


def read_file_safe(file_path: Path) -> Optional[str]:
    """Safely read file content with error handling"""
    try:
        return file_path.read_text(encoding='utf-8')
    except (IOError, UnicodeDecodeError):
        return None


def parse_toml_info(content: str) -> Optional[Dict[str, str]]:
    """Parse TOML manifest for addon info"""
    name_match = TOML_NAME_PATTERN.search(content)
    version_match = TOML_VERSION_PATTERN.search(content)

    if name_match:
        return {
            'name': name_match.group(1),
            'version': version_match.group(1) if version_match else 'Unknown',
            'type': 'Extension'
        }
    return None


def parse_bl_info(content: str) -> Optional[Dict[str, str]]:
    """Parse bl_info from Python content"""
    bl_info_match = BL_INFO_PATTERN.search(content)
    if not bl_info_match:
        return None

    bl_info_str = bl_info_match.group(1)
    name_match = BL_INFO_NAME_PATTERN.search(bl_info_str)
    version_match = BL_INFO_VERSION_PATTERN.search(bl_info_str)

    if name_match:
        name = name_match.group(1)
        version = 'Unknown'

        if version_match:
            version_tuple = version_match.group(1).replace(' ', '').split(',')
            version = '.'.join(v.strip() for v in version_tuple if v.strip())

        return {
            'name': name,
            'version': version,
            'type': 'Addon'
        }
    return None


def find_addon_root(file_path: str) -> Optional[AddonInfo]:
    """Addon root detection with caching"""
    if not file_path:
        return None

    current_path = Path(file_path)
    if not current_path.exists():
        return None

    # Search upwards from current directory
    for parent in [current_path.parent] + list(current_path.parent.parents):
        # Check for manifest first (Blender 4.2+)
        manifest_path = parent / ADDON_MANIFEST_FILE
        if manifest_path.exists():
            content = read_file_safe(manifest_path)
            if content:
                info = parse_toml_info(content)
                if info:
                    return AddonInfo(info['name'], info['version'], info['type'], str(parent))

        # Check for legacy __init__.py
        init_path = parent / ADDON_INIT_FILE
        if init_path.exists():
            content = read_file_safe(init_path)
            if content:
                info = parse_bl_info(content)
                if info:
                    return AddonInfo(info['name'], info['version'], info['type'], str(parent))

    return None


def parse_bl_info_from_text(text_content: str) -> Optional[Dict[str, Any]]:
    """Parse bl_info dictionary from text content"""
    try:
        bl_info_index = text_content.find("bl_info")
        if bl_info_index == -1:
            return None

        dict_start = text_content.find("{", bl_info_index)
        dict_end = text_content.find("}", dict_start)
        if dict_start == -1 or dict_end == -1:
            return None

        bl_info_code = text_content[dict_start:dict_end + 1]
        return ast.literal_eval(bl_info_code)
    except (ValueError, SyntaxError):
        return None


# -------------------------------------------------------------
#                    Core Addon Logic
# -------------------------------------------------------------

def get_addon_info(context) -> AddonInfo:
    """Get comprehensive addon information"""
    if not (context.space_data and context.space_data.text):
        return AddonInfo()

    text = context.space_data.text

    # Check for manual root directory setting
    if hasattr(text, 'install_settings') and text.install_settings.manual_root_dir:
        manual_root = text.install_settings.manual_root_dir
        manifest_path = Path(manual_root) / ADDON_MANIFEST_FILE
        init_path = Path(manual_root) / ADDON_INIT_FILE

        if manifest_path.exists():
            content = read_file_safe(manifest_path)
            if content:
                info = parse_toml_info(content)
                if info:
                    return AddonInfo(info['name'], info['version'], info['type'], manual_root)

        if init_path.exists():
            content = read_file_safe(init_path)
            if content:
                info = parse_bl_info(content)
                if info:
                    return AddonInfo(info['name'], info['version'], info['type'], manual_root)

    # Auto-detection from file path
    if text.filepath:
        file_path = bpy.path.abspath(text.filepath)
        addon_info = find_addon_root(file_path)
        if addon_info:
            return addon_info

    # Fallback: parse current script content
    if text and text.as_string():
        bl_info = parse_bl_info_from_text(text.as_string())
        if bl_info:
            name = bl_info.get("name", "Unknown")
            version = ".".join(str(v) for v in bl_info.get("version", []))
            root_dir = None

            if text.filepath:
                script_path = Path(bpy.path.abspath(text.filepath))
                if script_path.exists() and script_path.name != ADDON_INIT_FILE:
                    root_dir = str(script_path.parent)

            return AddonInfo(name, version, "Addon", root_dir)

    return AddonInfo()


def check_addon_installed(addon_info: AddonInfo) -> bool:
    """Check if addon is already installed"""
    if not addon_info.root_path:
        addon_name = addon_info.clean_name
    else:
        addon_name = Path(addon_info.root_path).name

    scripts_dir = Path(bpy.utils.user_resource('SCRIPTS')).parent / "scripts"
    extensions_dir = scripts_dir.parent / "extensions"

    possible_paths = [
        scripts_dir / "addons" / addon_name,
        scripts_dir / "addons" / f"{addon_name}.py",
        extensions_dir / "blender_org" / addon_name,
        extensions_dir / "user_default" / addon_name,
    ]

    return any(path.exists() for path in possible_paths)


# -------------------------------------------------------------
#                    Zip Generation
# -------------------------------------------------------------

class ZipGenerator:
    """Handles zip file creation for addons"""

    @staticmethod
    def get_zip_name(addon_info: AddonInfo, style: str) -> str:
        """Generate zip filename based on naming style"""
        clean_name = addon_info.clean_name
        version = addon_info.version

        if not version or version == "Unknown" or not version.strip():
            return f"{clean_name}.zip"

        if style == 'NAME_ONLY':
            return f"{clean_name}.zip"
        elif style == 'NAME_UNDERSCORE_VERSION':
            return f"{clean_name}_{version}.zip"
        elif style == 'NAME_DASH_VERSION':
            return f"{clean_name}-{version}.zip"

        return f"{clean_name}.zip"

    @staticmethod
    def create_zip(source_dir: str, zip_path: Path, arc_base: str) -> None:
        """Create zip file from source directory"""
        source_path = Path(source_dir)
        arc_base_path = Path(arc_base)

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in source_path.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(arc_base_path)
                    zipf.write(file_path, arcname=arcname)


# -------------------------------------------------------------
#                    Installation Logic
# -------------------------------------------------------------

class AddonInstaller:
    """Handles addon/extension installation"""

    def __init__(self, operator, context):
        self.operator = operator
        self.context = context
        self.install_settings = context.space_data.text.install_settings

    def report_error(self, message: str) -> Dict[str, str]:
        """Report error and return cancelled status"""
        self.operator.report({'ERROR'}, message)
        return {'CANCELLED'}

    def report_success(self, message: str) -> Dict[str, str]:
        """Report success and return finished status"""
        self.operator.report({'INFO'}, message)
        return {'FINISHED'}

    def handle_install_mode(self, module_name: str) -> None:
        """Handle disable/uninstall before installation"""
        if self.install_settings.install_mode == "DISABLE_INSTALL":
            try:
                bpy.ops.preferences.addon_disable(module=module_name)
            except:
                pass  # Ignore if addon not found
        elif self.install_settings.install_mode == "UNINSTALL_INSTALL":
            try:
                if "bl_ext." in module_name:
                    # Extension uninstall
                    addon_name = module_name.split(".")[-1]
                    bpy.ops.extensions.package_uninstall(
                        repo_index=1, pkg_id=addon_name)
                else:
                    # Addon uninstall
                    bpy.ops.preferences.addon_remove(module=module_name)
            except:
                pass  # Ignore if not found

    def open_preferences_if_needed(self, module_name: str) -> None:
        """Open addon preferences if requested"""
        if self.install_settings.open_preferences:
            try:
                bpy.ops.preferences.addon_expand(module=module_name)
                bpy.ops.preferences.addon_show(module=module_name)
            except:
                pass  # Ignore if fails

    def install_as_addon(self, zip_path: Path, addon_name: str) -> bool:
        """Install as traditional addon"""
        try:
            self.handle_install_mode(addon_name)
            bpy.ops.preferences.addon_install(
                filepath=str(zip_path), overwrite=True)
            bpy.ops.preferences.addon_enable(module=addon_name)
            self.open_preferences_if_needed(addon_name)
            return True
        except Exception as e:
            self.operator.report({'ERROR'}, f"Addon installation failed: {e}")
            return False

    def install_as_extension(self, zip_path: Path, addon_name: str) -> bool:
        """Install as Blender 4.2+ extension"""
        try:
            repo = self.install_settings.repo
            module_name = f"bl_ext.{repo}.{addon_name}"

            self.handle_install_mode(module_name)
            bpy.ops.extensions.package_install_files(
                filepath=str(zip_path),
                enable_on_install=False,
                overwrite=True,
                target="DEFAULT",
                repo=repo
            )
            bpy.ops.preferences.addon_enable(module=module_name)
            self.open_preferences_if_needed(module_name)
            return True
        except Exception as e:
            self.operator.report(
                {'ERROR'}, f"Extension installation failed: {e}")
            return False


# -------------------------------------------------------------
#                    Repository Management
# -------------------------------------------------------------

def repo_iter_valid_only(context, exclude_remote: bool = False, exclude_system: bool = True) -> Iterator[Any]:
    """Iterator for valid repositories"""
    if not (context and hasattr(context.preferences, 'extensions')):
        return

    for repo in context.preferences.extensions.repos:
        if exclude_system:
            if hasattr(repo, 'source') and repo.source == 'SYSTEM':
                continue
            if (hasattr(repo, 'is_system') and repo.is_system) or \
               (repo.name.lower() in SYSTEM_REPO_NAMES and
                    not repo.directory.startswith(bpy.utils.user_resource('EXTENSIONS'))):
                continue

        if exclude_remote and repo.use_remote_url:
            continue

        if repo.enabled:
            yield repo


def rna_prop_repo_enum_all_itemf(self, context) -> List[Tuple]:
    """Dynamic enum items for extension repositories"""
    if not context:
        result = []
    else:
        repos_valid = sorted(
            repo_iter_valid_only(
                context, exclude_remote=False, exclude_system=True),
            key=lambda repo: repo.name.casefold()
        )

        result = []
        has_local = has_remote = False

        # Add local repositories
        for repo in repos_valid:
            if repo.use_remote_url:
                has_remote = True
                continue
            has_local = True
            result.append((repo.module, repo.name, repo.directory,
                          'DISK_DRIVE', len(result)))

        # Add separator if needed
        if has_remote and has_local:
            result.append(None)

        # Add remote repositories
        for repo in repos_valid:
            if not repo.use_remote_url:
                continue
            result.append(
                (repo.module, repo.name, repo.remote_url, 'INTERNET', len(result)))

    # Prevent string garbage collection
    rna_prop_repo_enum_all_itemf.result = result
    return result


# -------------------------------------------------------------
#                    Property Groups
# -------------------------------------------------------------

def set_default_root_dir(self, context):
    """Set default root directory if not manually set"""
    if not self.manual_root_dir:
        text = context.space_data.text
        if text and text.filepath:
            path = Path(bpy.path.abspath(text.filepath)).parent
            if path.is_dir():
                self.manual_root_dir = str(path)


class ADDON_INSTALLER_PG_properties(bpy.types.PropertyGroup):
    open_preferences: bpy.props.BoolProperty(
        name="Open Preferences After Install",
        description="Open the Add-ons tab in Preferences after installing",
        default=False
    )

    install_mode: bpy.props.EnumProperty(
        name="Install Mode",
        description="Choose the addon installation method",
        items=[
            ('DISABLE_INSTALL', "Disable and Install",
             "Disable before installing, enable after"),
            ('UNINSTALL_INSTALL', "Uninstall and Install",
             "Uninstall before installing again"),
            ('NOTHING', "Do Nothing", "Install without disabling or uninstalling")
        ],
        default='DISABLE_INSTALL',
    )

    repo: bpy.props.EnumProperty(
        name="Repository",
        description="Choose the repository for the extension",
        items=rna_prop_repo_enum_all_itemf,
    )

    manual_root_dir: bpy.props.StringProperty(
        name="Manual Root Directory",
        description="Manually set the root directory containing __init__.py",
        update=set_default_root_dir
    )


# -------------------------------------------------------------
#                    Main Operation Logic
# -------------------------------------------------------------

def execute_addon_installation(operator, context) -> Dict[str, str]:
    """Main installation logic - refactored for clarity and performance"""
    addon_info = get_addon_info(context)
    prefs = get_addon_prefs(context)
    installer = AddonInstaller(operator, context)
    is_installed = check_addon_installed(addon_info)

    status_label = f"{'Reinstalled' if is_installed else 'Installed'} {addon_info.name}"

    # Handle addon with root directory
    if addon_info.root_path and (Path(addon_info.root_path) / ADDON_INIT_FILE).exists():
        return _install_from_directory(installer, addon_info, prefs, status_label)

    # Handle single script
    return _install_single_script(installer, addon_info, prefs, status_label, context)


def _install_from_directory(installer: AddonInstaller, addon_info: AddonInfo,
                            prefs, status_label: str) -> Dict[str, str]:
    """Install addon from directory structure"""
    root_path = Path(addon_info.root_path)
    parent_path = root_path.parent
    addon_name = root_path.name

    # Determine paths based on manual setting
    is_manual = installer.install_settings.manual_root_dir
    top_parent = parent_path.parent if is_manual else parent_path

    zip_name = ZipGenerator.get_zip_name(addon_info, prefs.zip_name_style)
    zip_path = top_parent / zip_name

    try:
        source = parent_path if is_manual else addon_info.root_path
        arc_base = parent_path.parent if is_manual else (
            parent_path if addon_info.addon_type == "Addon" else addon_info.root_path)

        ZipGenerator.create_zip(source, zip_path, arc_base)

        success = installer.install_as_addon(zip_path, addon_name) \
            if addon_info.addon_type == "Addon" \
            else installer.install_as_extension(zip_path, addon_name)

        if success:
            return installer.report_success(status_label)
        return {'CANCELLED'}

    except Exception as e:
        return installer.report_error(f"Failed to create zip: {e}")


def _install_single_script(installer: AddonInstaller, addon_info: AddonInfo,
                           prefs, status_label: str, context) -> Dict[str, str]:
    """Install single script as addon"""
    try:
        text_data = context.space_data.text

        if text_data.filepath:
            script_path = Path(bpy.path.abspath(text_data.filepath))
        else:
            # Create temporary file for unsaved script
            temp_dir = Path(tempfile.mkdtemp())
            script_path = temp_dir / "unsaved_script.py"
            script_path.write_text(text_data.as_string(), encoding="utf-8")

        script_dir = script_path.parent
        addon_name = addon_info.clean_name
        zip_name = ZipGenerator.get_zip_name(addon_info, prefs.zip_name_style)
        zip_path = script_dir / zip_name

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            arcname = str(Path(addon_name) / ADDON_INIT_FILE)
            zipf.write(script_path, arcname=arcname)

        installer.report_success(f"Script zipped as addon to:\n{zip_path}")

        success = installer.install_as_addon(zip_path, addon_name)
        return {'FINISHED'} if success else {'CANCELLED'}

    except Exception as e:
        installer.report_error(f"Script zip failed: {e}")
        return {'FINISHED'}


# -------------------------------------------------------------
#                    Operators
# -------------------------------------------------------------

class ADDON_INSTALLER_OT_install_addon(bpy.types.Operator):
    bl_idname = "textify.install_addon"
    bl_label = "Install Addon"
    bl_description = "Zips the addon and installs it (as addon or extension)"

    @classmethod
    def poll(cls, context):
        prefs = get_addon_prefs(context)
        return (prefs and prefs.enable_addon_installer and
                context.space_data and context.space_data.type == 'TEXT_EDITOR' and
                context.space_data.text is not None)

    def execute(self, context):
        return execute_addon_installation(self, context)


class ADDON_INSTALLER_OT_set_root_dir(bpy.types.Operator):
    bl_idname = "textify.set_root_dir"
    bl_label = "Set Root Directory"
    bl_description = "Set the root directory manually where __init__.py is located"

    directory: bpy.props.StringProperty(subtype="DIR_PATH")

    @classmethod
    def poll(cls, context):
        prefs = get_addon_prefs(context)
        return (prefs and prefs.enable_addon_installer and
                context.space_data and context.space_data.type == 'TEXT_EDITOR' and
                context.space_data.text is not None)

    def invoke(self, context, event):
        text = context.space_data.text
        if text and text.filepath:
            script_path = Path(bpy.path.abspath(text.filepath))
            self.directory = str(script_path.parent)

        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        install_settings = context.space_data.text.install_settings
        init_path = Path(self.directory) / ADDON_INIT_FILE

        if not init_path.exists():
            self.report(
                {'ERROR'}, "__init__.py not found in selected directory")
            return {'CANCELLED'}

        install_settings.manual_root_dir = str(init_path.parent)
        self.report({'INFO'}, f"Set manual root dir: {self.directory}")
        return {'FINISHED'}


# -------------------------------------------------------------
#                    UI Drawing
# -------------------------------------------------------------


def draw_installer_ui(layout, context):
    """Enhanced UI drawing function"""
    text = context.space_data.text if context.space_data else None

    if not text:
        layout.label(text="No script open")
        return

    addon_info = get_addon_info(context)
    install_settings = text.install_settings
    is_installed = check_addon_installed(addon_info)

    if addon_info.name == "Unknown Addon":
        if not text.as_string().strip():
            layout.label(text="Empty script")
            return
        else:
            layout.label(text="Not a valid addon script", icon='ERROR')
            layout.label(
                text="Missing bl_info dict or blender_manifest.toml", icon='DOT')

        if text.filepath:
            row = layout.row(align=True)
            row.prop(install_settings, "manual_root_dir",
                     text="Main Script Path")
            row.operator("textify.set_root_dir", text="", icon="FILE_FOLDER")
        return

    # Info display box
    box = layout.box()

    name_text = f"Name: {addon_info.name}"
    if text.is_dirty:
        name_text += " (unsaved)"
    box.label(text=name_text)
    box.label(text=f"Version: {addon_info.version}")
    box.label(text=f"Type: {addon_info.addon_type}")

    if addon_info.root_path:
        box.label(text=f"Root: {addon_info.root_path}")
    elif text.filepath and not Path(bpy.path.abspath(text.filepath)).exists():
        box.label(text="Directory: Not Found")
    else:
        box.label(text="Directory: Unknown")

    # Settings
    layout.use_property_split = True
    layout.use_property_decorate = False
    box = layout.box()
    box.prop(install_settings, "open_preferences")

    if addon_info.addon_type == "Extension":
        box.prop(install_settings, "repo")

    if is_installed:
        box.prop(install_settings, "install_mode")

    # Install button
    if context.region.type == 'UI':
        label = f"{'Reinstall' if is_installed else 'Install'} {addon_info.name}"
        row = layout.row()
        row.scale_y = 1.2
        row.operator("textify.install_addon", text=label)


class ADDON_INSTALLER_PT_zip_panel(bpy.types.Panel):
    bl_label = "Install Addon"
    bl_idname = "ADDON_INSTALLER_PT_zip_panel"
    bl_space_type = 'TEXT_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Text"

    @classmethod
    def poll(cls, context):
        prefs = get_addon_prefs(context)
        return (prefs and prefs.enable_addon_installer and
                prefs.enable_addon_installer_panel and
                context.space_data and context.space_data.type == 'TEXT_EDITOR' and
                context.space_data.text is not None)

    def draw(self, context):
        draw_installer_ui(self.layout, context)


class ADDON_INSTALLER_OT_install_popup(bpy.types.Operator):
    bl_idname = "textify.install_addon_popup"
    bl_label = "Install Addon"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        prefs = get_addon_prefs(context)
        return (prefs and prefs.enable_addon_installer and
                context.space_data and context.space_data.type == 'TEXT_EDITOR' and
                context.space_data.text is not None)

    def invoke(self, context, event):
        prefs = get_addon_prefs(context)
        addon_info = get_addon_info(context)
        is_installed = check_addon_installed(addon_info)
        title = f"{'Reinstall' if is_installed else 'Install'} {addon_info.name}"

        return context.window_manager.invoke_props_dialog(
            self, width=prefs.addon_installer_popup_width, title=title)

    def draw(self, context):
        draw_installer_ui(self.layout, context)

    def execute(self, context):
        return execute_addon_installation(self, context)


def draw_menu(self, context):
    """Add menu item to text editor"""
    if not (context.space_data.text and not context.space_data.text.is_in_memory):
        return

    addon_info = get_addon_info(context)
    if addon_info.name != "Unknown Addon":
        is_installed = check_addon_installed(addon_info)
        label = f"{'Reinstall' if is_installed else 'Install'} {addon_info.name}"

        layout = self.layout
        layout.separator()
        layout.operator("textify.install_addon_popup", text=label)


# -------------------------------------------------------------
#                    Registration
# -------------------------------------------------------------

classes = [
    ADDON_INSTALLER_PG_properties,
    ADDON_INSTALLER_OT_install_addon,
    ADDON_INSTALLER_OT_set_root_dir,
    ADDON_INSTALLER_OT_install_popup,
]


def register():
    try:
        for cls in classes:
            bpy.utils.register_class(cls)

        bpy.types.Text.install_settings = bpy.props.PointerProperty(
            type=ADDON_INSTALLER_PG_properties)

        bpy.types.TEXT_MT_text.append(draw_menu)
    except Exception as e:
        print(f"Registration error: {e}")


def unregister():
    try:
        for cls in classes:
            bpy.utils.unregister_class(cls)

        del bpy.types.Text.install_settings
        bpy.types.TEXT_MT_text.remove(draw_menu)
    except Exception as e:
        print(f"Unregistration error: {e}")
