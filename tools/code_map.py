import bpy
import re
import ast
from bpy.props import StringProperty, BoolProperty, IntProperty
from bpy.types import Panel, Operator, PropertyGroup
from .. import textify_icons

# Constants
MAX_PREVIEW_LENGTH = 50


# -------------------------------------------------------------
#                           Function
# -------------------------------------------------------------


def get_addon_prefs(context):
    """Get addon preferences safely"""
    try:
        for addon_id in context.preferences.addons.keys():
            if 'textify' in addon_id.lower():
                return context.preferences.addons[addon_id].preferences
    except (AttributeError, KeyError):
        pass
    return None


# -------------------------------------------------------------
#                        Property Group
# -------------------------------------------------------------


class CODE_MAP_PG_Properties(PropertyGroup):
    """Property group for storing code map settings and filters"""
    search_text: StringProperty(
        name="Search", description="Search for classes, functions, and properties", default="", options={'TEXTEDIT_UPDATE'})
    show_classes: BoolProperty(name="Show Classes", default=True)
    show_methods: BoolProperty(name="Show Methods", default=True)
    show_properties: BoolProperty(name="Show Properties", default=True)
    show_functions: BoolProperty(name="Show Functions", default=True)
    show_variables: BoolProperty(name="Show Variables", default=True)
    show_constants: BoolProperty(name="Show Constants", default=True)


# -------------------------------------------------------------
#                          Operators
# -------------------------------------------------------------


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
            self.VARIABLE_PATTERN = re.compile(
                r'^\s*([A-Z_][A-Z0-9_]*|[a-zA-Z_]\w*)\s*=\s*')
            self.CONSTANT_PATTERN = re.compile(r'^\s*([A-Z_][A-Z0-9_]*)\s*=')
            CodePatterns._initialized = True


class CodeItem:
    """Represents a code item (class, function, property, variable, constant)"""

    def __init__(self, name, item_type, line_number, indent_level, parent=None):
        self.name = name
        self.item_type = item_type
        self.line_number = line_number
        self.indent_level = indent_level
        self.parent = parent
        self.children = []
        self.is_expanded = True
        self.end_line = None
        self.bl_idname = None
        self.value_preview = None

    def add_child(self, child):
        child.parent = self
        self.children.append(child)

    def get_full_path(self):
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
                    if hasattr(node, 'value'):
                        item.value_preview = self._extract_value_preview(
                            node.value, lines[node.lineno - 1])

    def _extract_value_preview(self, value_node, line_text):
        try:
            if isinstance(value_node, ast.Constant):
                return str(value_node.value)[:MAX_PREVIEW_LENGTH]
            return None
        except:
            return None

    def _fallback_end_lines(self, items, lines):
        for item in items:
            if item.end_line is None:
                item.end_line = item.line_number if item.item_type in [
                    'property', 'variable', 'constant'] else self._guess_end_line(item, lines)
            self._fallback_end_lines(item.children, lines)

    def _guess_end_line(self, item, lines):
        start = item.line_number - 1
        if start >= len(lines):
            return item.line_number
        base_indent = len(lines[start]) - len(lines[start].lstrip())
        for i in range(start + 1, len(lines)):
            if lines[i].strip() and len(lines[i]) - len(lines[i].lstrip()) <= base_indent:
                return i
        return len(lines)

    def _get_end_line(self, node, lines):
        return node.end_lineno if hasattr(node, 'end_lineno') and node.end_lineno else self._guess_end_line(node, lines)

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
        lines = text.split('\n')
        items = []
        stack = []

        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue

            indent = len(line) - len(line.lstrip())
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

    def _parse_line(self, line, line_num, indent, parent_type=None, full_line=""):
        # Class parsing
        m = self.patterns.CLASS_PATTERN.match(line)
        if m:
            return CodeItem(m.group(1), 'class', line_num, indent)

        # Function parsing
        m = self.patterns.FUNCTION_PATTERN.match(line)
        if m:
            kind = 'method' if parent_type in {
                'class', 'function'} else 'function'
            return CodeItem(m.group(1), kind, line_num, indent)

        # Property parsing
        m = self.patterns.PROPERTY_PATTERN.match(line)
        if m and ':' in line and not line.startswith('#') and '=' not in line:
            return CodeItem(m.group(1), 'property', line_num, indent)

        # Variable/Constant parsing (only at module level)
        if parent_type is None:
            m = self.patterns.CONSTANT_PATTERN.match(line)
            if m and m.group(1).isupper():
                return self._create_variable_item(m.group(1), 'constant', line_num, indent, full_line)

            m = self.patterns.VARIABLE_PATTERN.match(line)
            if m and not m.group(1).isupper():
                return self._create_variable_item(m.group(1), 'variable', line_num, indent, full_line)

        return None

    def _create_variable_item(self, name, item_type, line_num, indent, full_line):
        """Helper to create variable/constant items with value preview"""
        item = CodeItem(name, item_type, line_num, indent)
        if '=' in full_line:
            value_part = full_line.split('=', 1)[1].strip()
            item.value_preview = value_part[:MAX_PREVIEW_LENGTH] + \
                ("..." if len(value_part) > MAX_PREVIEW_LENGTH else "")
        return item


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
        self.code_items = items

    def toggle_expansion(self, item_path):
        if item_path in self.expanded_items:
            self.expanded_items.remove(item_path)
        else:
            self.expanded_items.add(item_path)

    def is_expanded(self, item_path):
        return item_path in self.expanded_items

    def needs_update(self, context):
        if not context.space_data.text:
            if self.current_text_name != "":
                self.current_text_name = ""
                self.code_items = []
                return True
            return False

        text = context.space_data.text
        current_name = text.name if text else ""

        if self.current_text_name != current_name:
            self.current_text_name = current_name
            self.last_text_hash = 0
            return True

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

        if event.ctrl:
            if self.item_type == 'class' and self.item_bl_idname:
                clipboard_helper.copy_to_clipboard(self.item_bl_idname)
                self.report(
                    {'INFO'}, f"Copied bl_idname: {self.item_bl_idname}")
            else:
                self.report(
                    {'WARNING'}, "No bl_idname available for this item")
            return {'FINISHED'}
        elif event.shift:
            clipboard_helper.copy_to_clipboard(self.item_name)
            self.report({'INFO'}, f"Copied name: {self.item_name}")
            return {'FINISHED'}
        elif event.alt:
            if context.space_data.text:
                if not self.item_end_line:
                    self.item_end_line = self.line_number
                self._select_code_block(context)
                self.report(
                    {'INFO'}, f"Selected {self.item_type}: {self.item_name}")
            else:
                self.report(
                    {'WARNING'}, "Cannot determine code block boundaries")
            return {'FINISHED'}
        else:
            return self.execute(context)

    def _select_code_block(self, context):
        text = context.space_data.text
        if not text:
            return

        bpy.ops.text.jump(line=self.line_number)
        bpy.ops.text.move(type='LINE_BEGIN')

        start_line_index = self.line_number - 1
        end_line_index = min(self.item_end_line - 1, len(text.lines) - 1)

        if start_line_index < len(text.lines):
            start_line_body = text.lines[start_line_index].body
            start_column = len(start_line_body) - len(start_line_body.lstrip())
        else:
            start_column = 0

        end_column = len(text.lines[end_line_index].body) if end_line_index < len(
            text.lines) else 0

        if self.line_number == self.item_end_line:
            text.select_set(start_line_index, start_column, start_line_index, len(
                text.lines[start_line_index].body))
        else:
            text.select_set(start_line_index, start_column,
                            end_line_index, end_column)

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
        NavigationState().toggle_expansion(self.item_path)
        context.area.tag_redraw()
        return {'FINISHED'}


# -------------------------------------------------------------
#                              UI
# -------------------------------------------------------------


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
            if item.item_type in {"function", "method"}:
                start, end = item.line_number, item.end_line or item.line_number
                if start <= cursor_line <= end:
                    return item.name, item.line_number
        return None, None

    @staticmethod
    def _find_active_class(items, cursor_line):
        for item in items:
            if item.item_type == "class":
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
        def is_visible(item):
            visibility_map = {
                "class": nav_data.show_classes,
                "property": nav_data.show_properties,
                "variable": nav_data.show_variables,
                "constant": nav_data.show_constants,
                "function": nav_data.show_methods if item.parent and item.parent.item_type in {"class", "function"} else nav_data.show_functions
            }
            return visibility_map.get(item.item_type, True)

        def filter_recursive(items):
            result = []
            for item in items:
                if is_visible(item) and (search_text.lower() in item.name.lower() or any(self._item_matches_search(c, search_text) for c in item.children)):
                    new_item = item
                    new_item.children = filter_recursive(item.children)
                    result.append(new_item)
            return result

        return filter_recursive(items)

    def _item_matches_search(self, item, search_text):
        return search_text.lower() in item.name.lower() or any(self._item_matches_search(child, search_text) for child in item.children)

    def draw_code_item(self, layout, item, level=0, nav_state=None, active_class=None, active_function=None, active_function_line=None):
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

        # Icon + operator
        icon_name = 'constant' if item.item_type == 'constant' else item.item_type
        icon = textify_icons.get_icon(icon_name)
        icon_id = icon.icon_id if icon else 0
        sub = row.row(align=True)
        sub.alignment = 'LEFT'

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

        # Active indicator
        show_active = (
            (item.item_type in {"function", "method"} and item.name == active_function and item.line_number == active_function_line) or
            (item.item_type == "class" and item.name ==
             active_class and not nav_state.is_expanded(item.get_full_path()))
        )

        if show_active:
            row.label(text="", icon="LAYER_ACTIVE")

        # Draw children if expanded
        if item.children and nav_state.is_expanded(item.get_full_path()):
            for child in item.children:
                self.draw_code_item(layout, child, level + 1, nav_state,
                                    active_class, active_function, active_function_line)

    @staticmethod
    def draw_code_map_ui(layout, context, prefs):
        nav_data = context.scene.code_navigation

        # Search bar
        row = layout.row()
        if prefs and getattr(prefs, 'auto_activate_search', False):
            row.activate_init = True
        row.prop(nav_data, "search_text", icon='VIEWZOOM', text="")

        # Toggle filters
        if prefs.show_code_filters:
            layout.separator(factor=0.05)
            CodeRenderer._draw_toggle_filter_row(layout, nav_data)

        layout.separator(factor=0.05)

        # Update navigation state
        nav_state = NavigationState()
        if nav_state.needs_update(context):
            text = context.space_data.text
            if text:
                nav_state.update_code_items(
                    CodeAnalyzer().analyze_text(text.as_string()))

        # Compute active items
        cursor_line = context.space_data.text.current_line_index + 1
        active_function, active_function_line = CodeRenderer._find_active_function(
            nav_state.code_items, cursor_line)
        active_class = CodeRenderer._find_active_class(
            nav_state.code_items, cursor_line)

        # Filter and draw
        renderer = CodeRenderer()
        items = renderer.filter_items(
            nav_state.code_items, nav_data.search_text, nav_data)
        if not items:
            layout.label(
                text="No matches found" if nav_data.search_text else "No code structure found")
            return

        for item in items:
            renderer.draw_code_item(layout, item, nav_state=nav_state, active_class=active_class,
                                    active_function=active_function, active_function_line=active_function_line)

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
        return (prefs.enable_code_map and
                context.space_data and
                context.space_data.type == 'TEXT_EDITOR' and
                context.space_data.text is not None)

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
        return (prefs.enable_code_map and
                prefs.show_code_map_panel and
                context.space_data and
                context.space_data.type == 'TEXT_EDITOR' and
                context.space_data.text is not None)

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
