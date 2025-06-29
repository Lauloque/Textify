import bpy
import re
import ast
from bpy.props import StringProperty, BoolProperty, IntProperty, EnumProperty
from bpy.types import Panel, Operator, PropertyGroup


from .. import textify_icons


def get_addon_prefs(context):
    """Get addon preferences safely"""
    try:
        for addon_id in context.preferences.addons.keys():
            if 'textify' in addon_id.lower():
                return context.preferences.addons[addon_id].preferences
    except (AttributeError, KeyError):
        pass
    return None


class CodePatterns:
    """Singleton class for pre-compiled regex patterns"""
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.CLASS_PATTERN = re.compile(r'^\s*class\s+(\w+)\s*[\(:]')
            self.FUNCTION_PATTERN = re.compile(r'^\s*def\s+(\w+)\s*\(')
            self.PROPERTY_PATTERN = re.compile(r'^\s*([\w]+)\s*:\s*[\w\[\]]+')
            self.BASE_CLASS_PATTERN = re.compile(
                r'class\s+\w+\s*\(\s*([\w\.]+)')
            self.FUNCTION_SIG_PATTERN = re.compile(r"def\s+(\w+)\s*\((.*?)\)")
            # Enhanced variable pattern to handle constants, dictionaries, and complex assignments
            self.VARIABLE_PATTERN = re.compile(
                r'^\s*([A-Z_][A-Z0-9_]*|[a-zA-Z_]\w*)\s*=\s*')
            # Pattern specifically for dictionary/set assignments
            self.DICT_SET_PATTERN = re.compile(
                r'^\s*([a-zA-Z_]\w*)\s*=\s*[\{\[]')
            # Pattern for constants (all uppercase with underscores)
            self.CONSTANT_PATTERN = re.compile(r'^\s*([A-Z_][A-Z0-9_]*)\s*=')
            CodePatterns._initialized = True


class CodeItem:
    """Represents a code item (class, function, property, variable, constant)"""

    def __init__(self, name, item_type, line_number, indent_level, parent=None):
        self.name = name
        self.item_type = item_type  # 'class', 'function', 'property', 'variable', 'constant'
        self.line_number = line_number
        self.indent_level = indent_level
        self.parent = parent
        self.children = []
        self.is_expanded = True
        self.end_line = None  # Will be set by AST analyzer
        self.bl_idname = None  # For Blender operators/panels
        self.value_preview = None  # For showing variable/constant values

    def add_child(self, child):
        """Add a child item"""
        child.parent = self
        self.children.append(child)

    def get_full_path(self):
        """Get the full path of the item"""
        path = []
        current = self
        while current:
            path.append(current.name)
            current = current.parent
        return ".".join(reversed(path))


class ASTAnalyzer:
    """Singleton class for AST-based code enhancement"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def enhance_items_with_ast(self, items, text):
        lines = text.split('\n')
        try:
            tree = ast.parse(text)
            self._process_ast(tree, items, lines)
        except SyntaxError:
            self._fallback_end_lines(items, lines)

    def _process_ast(self, tree, items, lines):
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                item = self._find_by_lineno(items, node.lineno)
                if item:
                    item.end_line = self._get_end_line(node, lines)
                    if isinstance(node, ast.ClassDef):
                        item.bl_idname = self._extract_bl_idname(node)
            elif isinstance(node, ast.Assign):
                item = self._find_by_lineno(items, node.lineno)
                if item and item.item_type in ['property', 'variable', 'constant']:
                    item.end_line = node.lineno
                    # Extract value preview for variables/constants
                    if hasattr(node, 'value'):
                        item.value_preview = self._extract_value_preview(
                            node.value, lines[node.lineno - 1])

    def _extract_value_preview(self, value_node, line_text):
        """Extract a preview of the assigned value"""
        try:
            if isinstance(value_node, ast.Constant):
                return str(value_node.value)[:50]
            # Skip preview for non-constants
            return None
        except:
            return None

    def _fallback_end_lines(self, items, lines):
        for item in items:
            if item.end_line is None:
                if item.item_type in ['property', 'variable', 'constant']:
                    item.end_line = item.line_number
                else:
                    item.end_line = self._guess_end_line(item, lines)
            self._fallback_end_lines(item.children, lines)

    def _guess_end_line(self, item, lines):
        start = item.line_number - 1
        if start >= len(lines):
            return item.line_number
        base_indent = len(lines[start]) - len(lines[start].lstrip())
        for i in range(start + 1, len(lines)):
            if not lines[i].strip():
                continue
            current_indent = len(lines[i]) - len(lines[i].lstrip())
            if current_indent <= base_indent:
                return i
        return len(lines)

    def _get_end_line(self, node, lines):
        if hasattr(node, 'end_lineno') and node.end_lineno:
            return node.end_lineno
        return self._guess_end_line(node, lines)

    def _find_by_lineno(self, items, lineno):
        for item in items:
            if item.line_number == lineno:
                return item
            found = self._find_by_lineno(item.children, lineno)
            if found:
                return found
        return None

    def _extract_bl_idname(self, class_node):
        for node in class_node.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == 'bl_idname':
                        val = node.value
                        if isinstance(val, ast.Constant):
                            return val.value
                        if isinstance(val, ast.Str):
                            return val.s
        return None


class ClipboardHelper:
    """Singleton class for clipboard operations"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def copy_to_clipboard(self, text):
        """Copy text to clipboard"""
        bpy.context.window_manager.clipboard = text


class CodeAnalyzer:
    """Singleton class for analyzing code structure with AST enhancement"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self.patterns = CodePatterns()

    def analyze_text(self, text):
        """Analyze text and return structured code items"""
        lines = text.split('\n')
        items = []
        stack = []

        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue

            indent = self._get_indent_level(line)
            while stack and stack[-1].indent_level >= indent:
                stack.pop()

            parent_type = stack[-1].item_type if stack else None
            item = self._parse_line(
                stripped, line_num, indent, parent_type, line)
            if item:
                (stack[-1].add_child(item) if stack else items.append(item))
                if item.item_type in {'class', 'function', 'method'}:
                    stack.append(item)

        ASTAnalyzer().enhance_items_with_ast(items, text)
        return items

    def _get_indent_level(self, line):
        return len(line) - len(line.lstrip())

    def _parse_line(self, line, line_num, indent, parent_type=None, full_line=""):
        """Parse a line and return a CodeItem if it matches"""
        if (m := self.patterns.CLASS_PATTERN.match(line)):
            return CodeItem(m.group(1), 'class', line_num, indent)

        if (m := self.patterns.FUNCTION_PATTERN.match(line)):
            kind = 'method' if parent_type in {
                'class', 'function'} else 'function'
            return CodeItem(m.group(1), kind, line_num, indent)

        if (m := self.patterns.PROPERTY_PATTERN.match(line)):
            if ':' in line and not line.startswith('#') and '=' not in line:
                return CodeItem(m.group(1), 'property', line_num, indent)

        # Check for constants (all uppercase with underscores)
        if parent_type is None and (m := self.patterns.CONSTANT_PATTERN.match(line)):
            name = m.group(1)
            if name.isupper():
                item = CodeItem(name, 'constant', line_num, indent)
                if '=' in full_line:
                    value_part = full_line.split('=', 1)[1].strip()
                    item.value_preview = value_part[:50] + \
                        ("..." if len(value_part) > 50 else "")
                return item

        # Check for regular variables
        if parent_type is None and (m := self.patterns.VARIABLE_PATTERN.match(line)):
            name = m.group(1)
            if not name.isupper():
                item = CodeItem(name, 'variable', line_num, indent)
                if '=' in full_line:
                    value_part = full_line.split('=', 1)[1].strip()
                    item.value_preview = value_part[:50] + \
                        ("..." if len(value_part) > 50 else "")
                return item

        return None


class CODE_MAP_PG_Properties(PropertyGroup):
    """Property group for storing code map settings and filters"""

    search_text: StringProperty(
        name="Search",
        description="Search for classes, functions, and properties",
        default="",
        options={'TEXTEDIT_UPDATE'}
    )

    show_classes: BoolProperty(name="Show Classes", default=True)
    show_methods: BoolProperty(name="Show Methods", default=True)
    show_properties: BoolProperty(name="Show Properties", default=True)
    show_functions: BoolProperty(name="Show Functions", default=True)
    show_variables: BoolProperty(name="Show Variables", default=True)
    show_constants: BoolProperty(name="Show Constants", default=True)


class NavigationState:
    """Singleton class for managing navigation state"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.code_items = []
            cls._instance.expanded_items = set()
            cls._instance.current_text_name = ""
            cls._instance.last_text_hash = 0
        return cls._instance

    def update_code_items(self, items):
        """Update the code items"""
        self.code_items = items

    def toggle_expansion(self, item_path):
        """Toggle expansion state of an item"""
        if item_path in self.expanded_items:
            self.expanded_items.remove(item_path)
        else:
            self.expanded_items.add(item_path)

    def is_expanded(self, item_path):
        """Check if an item is expanded"""
        return item_path in self.expanded_items

    def needs_update(self, context):
        """Check if the code structure needs to be updated"""
        if not context.space_data.text:
            if self.current_text_name != "":
                self.current_text_name = ""
                self.code_items = []
                return True
            return False

        text = context.space_data.text
        current_name = text.name if text else ""

        # Check if text file changed
        if self.current_text_name != current_name:
            self.current_text_name = current_name
            self.last_text_hash = 0  # Force update
            return True

        # Check if content changed
        if text:
            current_hash = hash(text.as_string())
            if self.last_text_hash != current_hash:
                self.last_text_hash = current_hash
                return True

        return False


class CODE_MAP_OT_jump_to_line(Operator):
    """Jump to a specific line in the text editor"""
    bl_idname = "text.jump_to_line"
    bl_label = "Jump to Line"
    bl_description = "Jump to the specified line"

    line_number: IntProperty()
    item_name: StringProperty()
    item_type: StringProperty()
    item_bl_idname: StringProperty()
    item_end_line: IntProperty()

    def invoke(self, context, event):
        clipboard_helper = ClipboardHelper()

        # Ctrl: Copy bl_idname to clipboard (only for classes with bl_idname)
        if event.ctrl:
            if self.item_type == 'class' and self.item_bl_idname:
                clipboard_helper.copy_to_clipboard(self.item_bl_idname)
                self.report(
                    {'INFO'}, f"Copied bl_idname: {self.item_bl_idname}")
            else:
                self.report(
                    {'WARNING'}, "No bl_idname available for this item")
            return {'FINISHED'}

        # Shift: Copy item name to clipboard
        elif event.shift:
            clipboard_helper.copy_to_clipboard(self.item_name)
            self.report({'INFO'}, f"Copied name: {self.item_name}")
            return {'FINISHED'}

        # Alt: Select code block using AST information
        elif event.alt:
            if context.space_data.text:
                # fallback if end_line is not set
                if not self.item_end_line:
                    self.item_end_line = self.line_number

                self._select_code_block(context)
                self.report(
                    {'INFO'}, f"Selected {self.item_type}: {self.item_name}")
            else:
                self.report(
                    {'WARNING'}, "Cannot determine code block boundaries")
            return {'FINISHED'}

        # Default behavior: Jump to line
        else:
            return self.execute(context)

    def _select_code_block(self, context):
        """Select the entire code block from start to end line"""
        text = context.space_data.text
        if not text:
            return

        # Jump to start line
        bpy.ops.text.jump(line=self.line_number)

        # Move to beginning of line
        bpy.ops.text.move(type='LINE_BEGIN')

        # Calculate end position (end of the last line)
        end_line_index = self.item_end_line - 1
        if end_line_index < len(text.lines):
            end_column = len(text.lines[end_line_index].body)
        else:
            end_line_index = len(text.lines) - 1
            end_column = len(text.lines[end_line_index].body)

        # Select from start of first line to end of last line
        # Handle single-line (e.g., properties)
        start_line_index = self.line_number - 1
        if start_line_index < len(text.lines):
            start_line_body = text.lines[start_line_index].body
            start_column = len(start_line_body) - len(start_line_body.lstrip())
        else:
            start_column = 0

        # Handle single-line (e.g., properties)
        if self.line_number == self.item_end_line:
            text.select_set(start_line_index, start_column, start_line_index, len(
                text.lines[start_line_index].body))
        else:
            text.select_set(start_line_index, start_column,
                            end_line_index, end_column)

        # Ensure the selection is visible
        context.area.tag_redraw()

    def execute(self, context):
        if context.space_data.text:
            bpy.ops.text.jump(line=self.line_number)
        return {'FINISHED'}


class CODE_MAP_OT_toggle_item(Operator):
    """Toggle expansion of code items"""
    bl_idname = "text.toggle_code_item"
    bl_label = "Toggle Code Item"
    bl_description = "Expand or collapse code item"

    item_path: StringProperty()

    def execute(self, context):
        nav_state = NavigationState()
        nav_state.toggle_expansion(self.item_path)
        context.area.tag_redraw()
        return {'FINISHED'}


class CodeRenderer:
    """Singleton class for rendering code navigation UI"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @staticmethod
    def _find_active_function(items, cursor_line):
        for item in CodeRenderer._flatten_items(items):
            if item.item_type not in {"function", "method"}:
                continue
            start, end = item.line_number, item.end_line or item.line_number
            if start <= cursor_line <= end:
                return item.name, item.line_number
        return None, None

    @staticmethod
    def _find_active_class(items, cursor_line):
        for item in items:
            if item.item_type != "class":
                continue
            start, end = item.line_number, item.end_line or item.line_number
            if start <= cursor_line <= end:
                return item.name
        return None

    @staticmethod
    def _flatten_items(items):
        result = []
        for item in items:
            result.append(item)
            result.extend(CodeRenderer._flatten_items(item.children))
        return result

    def filter_items(self, items, search_text, nav_data):
        """Filter items based on search text and toggles"""
        def is_visible(item):
            if item.item_type == "class" and not nav_data.show_classes:
                return False
            if item.item_type == "function":
                if item.parent and item.parent.item_type in {"class", "function"}:
                    return nav_data.show_methods
                return nav_data.show_functions
            if item.item_type == "property":
                return nav_data.show_properties
            if item.item_type == "variable":
                return nav_data.show_variables
            if item.item_type == "constant":
                return nav_data.show_constants
            return True

        def filter_recursive(items):
            result = []
            for item in items:
                if not is_visible(item):
                    continue
                if search_text.lower() in item.name.lower() or any(self._item_matches_search(c, search_text) for c in item.children):
                    new_item = item
                    new_item.children = filter_recursive(item.children)
                    result.append(new_item)
            return result

        return filter_recursive(items)

    def _is_item_active(self, item, active_class, active_function, active_function_line):
        if item.item_type == "class":
            return item.name == active_class
        if item.item_type in {"function", "method"}:
            return item.name == active_function and item.line_number == active_function_line
        return False

    def _item_matches_search(self, item, search_text):
        if search_text.lower() in item.name.lower():
            return True
        return any(self._item_matches_search(child, search_text) for child in item.children)

    def draw_code_item(self, layout, item, level=0, nav_state=None,
                       active_class=None, active_function=None, active_function_line=None):
        if nav_state is None:
            nav_state = NavigationState()

        row = layout.row(align=True)

        # Indentation
        for _ in range(level):
            row.label(text="", icon='BLANK1')

        # Toggle
        if item.children:
            item_path = item.get_full_path()
            is_expanded = nav_state.is_expanded(item_path)
            icon = 'DOWNARROW_HLT' if is_expanded else 'RIGHTARROW'
            toggle = row.operator("text.toggle_code_item",
                                  text="", icon=icon, emboss=False)
            toggle.item_path = item_path
        else:
            row.label(text="", icon='BLANK1')

        # Custom icon + operator
        icon_name = 'constant' if item.item_type == 'constant' else item.item_type
        icon = textify_icons.get_icon(icon_name)
        icon_id = icon.icon_id if icon else 0
        sub = row.row(align=True)
        sub.alignment = 'LEFT'

        # Display name with value preview for variables/constants
        display_text = item.name
        if item.item_type in ['variable', 'constant'] and item.value_preview:
            display_text = f"{item.name} = {item.value_preview}"

        op = sub.operator("text.jump_to_line", text=display_text,
                          icon_value=icon_id, emboss=False)
        op.line_number = item.line_number
        op.item_name = item.name
        op.item_type = item.item_type
        op.item_bl_idname = item.bl_idname or ""
        op.item_end_line = item.end_line or 0

        # Active indicator (mutually exclusive)
        show_active = False

        if item.item_type in {"function", "method"}:
            if self._is_item_active(item, active_class, active_function, active_function_line):
                show_active = True

        elif item.item_type == "class":
            # Show active icon only if class is active AND not expanded
            if item.name == active_class and not nav_state.is_expanded(item.get_full_path()):
                show_active = True

        if show_active:
            row.label(text="", icon="LAYER_ACTIVE")

        # Draw children if expanded
        if item.children and nav_state.is_expanded(item.get_full_path()):
            for child in item.children:
                self.draw_code_item(
                    layout, child, level + 1, nav_state,
                    active_class=active_class,
                    active_function=active_function,
                    active_function_line=active_function_line
                )

    @staticmethod
    def draw_code_map_ui(layout, context, prefs):
        nav_data = context.scene.code_navigation

        # Search bar
        row = layout.row()
        if prefs and getattr(prefs, 'auto_activate_search', False):
            row.activate_init = True
        row.prop(nav_data, "search_text", icon='VIEWZOOM', text="")

        # Toggle filters row
        if prefs.show_code_filters:
            layout.separator(factor=0.05)
            CodeRenderer._draw_toggle_filter_row(layout, nav_data)

        layout.separator(factor=0.05)

        # Update navigation state if needed
        nav_state = NavigationState()
        if nav_state.needs_update(context):
            text = context.space_data.text
            if text:
                analyzer = CodeAnalyzer()
                nav_state.update_code_items(
                    analyzer.analyze_text(text.as_string()))

        # Compute active items
        cursor_line = context.space_data.text.current_line_index + 1
        active_function, active_function_line = CodeRenderer._find_active_function(
            nav_state.code_items, cursor_line)
        active_class = CodeRenderer._find_active_class(
            nav_state.code_items, cursor_line)

        # Filter and draw code items
        renderer = CodeRenderer()
        items = renderer.filter_items(
            nav_state.code_items, nav_data.search_text, nav_data)
        if not items:
            layout.label(
                text="No matches found" if nav_data.search_text else "No code structure found")
            return

        for item in items:
            renderer.draw_code_item(
                layout, item, nav_state=nav_state,
                active_class=active_class,
                active_function=active_function,
                active_function_line=active_function_line
            )

    @staticmethod
    def _draw_toggle_filter_row(layout, nav_data):
        row = layout.row(align=True)
        row.scale_x = 5.0

        icons = ["class", "method", "function",
                 "property", "variable", "constant"]
        props = ["show_classes", "show_methods", "show_functions",
                 "show_properties", "show_variables", "show_constants"]

        for prop, icon_name in zip(props, icons):
            icon = textify_icons.get_icon(icon_name)
            icon_id = icon.icon_id if icon else 0
            row.prop(nav_data, prop, toggle=True, text="", icon_value=icon_id)


class CODE_MAP_OT_popup(Operator):
    """Code map popup operator"""
    bl_idname = "code_map.popup"
    bl_label = "Code Map"

    @classmethod
    def poll(cls, context):
        prefs = get_addon_prefs(context)
        return (prefs and getattr(prefs, 'enable_code_map', False))

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        prefs = get_addon_prefs(context)
        width = getattr(prefs, 'code_map_popup_width', 400) if prefs else 400
        return context.window_manager.invoke_props_dialog(self, width=width)

    def draw(self, context):
        prefs = get_addon_prefs(context)
        CodeRenderer.draw_code_map_ui(self.layout, context, prefs)


class CODE_MAP_PT_panel(Panel):
    """Code map panel in text editor"""
    bl_idname = "CODE_MAP_PT_panel"
    bl_label = "Code Map"
    bl_space_type = 'TEXT_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Code Map"

    @classmethod
    def poll(cls, context):
        prefs = get_addon_prefs(context)
        return (prefs and
                getattr(prefs, 'enable_code_map', False) and
                getattr(prefs, 'show_code_map_panel', True))

    def draw(self, context):
        prefs = get_addon_prefs(context)
        CodeRenderer.draw_code_map_ui(self.layout, context, prefs)


# Registration
classes = [
    CODE_MAP_PG_Properties,
    CODE_MAP_OT_jump_to_line,
    CODE_MAP_OT_toggle_item,
    CODE_MAP_OT_popup,
    CODE_MAP_PT_panel,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.code_navigation = bpy.props.PointerProperty(
        type=CODE_MAP_PG_Properties)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.code_navigation
