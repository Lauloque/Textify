import bpy
import ast


class ASTDefinitionFinder:
    def __init__(self, source_code, target_word):
        self.source_code = source_code
        self.target_word = target_word
        self.definitions = []
        self.scopes = []  # Track scope stack
        self.current_line = 0  # Track current line for scope-aware searching

    def find_definitions(self):
        try:
            tree = ast.parse(self.source_code)
            self.visit_node(tree)
            # Sort definitions by line number and return closest ones first
            self.definitions.sort(key=lambda x: x['line'])
            return self.definitions
        except SyntaxError:
            return []

    def is_valid_identifier(self, name):
        """Check if the name is a valid Python identifier"""
        return name and name.isidentifier() and not name.startswith('__')

    def add_definition(self, node, def_type, name=None):
        """Add a definition with scope information"""
        if name is None:
            name = getattr(node, 'name', None) or getattr(node, 'id', None)

        if name == self.target_word and self.is_valid_identifier(name):
            self.definitions.append({
                'line': node.lineno - 1,
                'column': node.col_offset,
                'type': def_type,
                'scope_depth': len(self.scopes),
                'name': name
            })

    def visit_node(self, node, parent_line=0):
        # Track current position for scope-aware searching
        if hasattr(node, 'lineno'):
            self.current_line = node.lineno

        # Function definitions
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            self.add_definition(node, 'async_function' if isinstance(node, ast.AsyncFunctionDef) else 'function')

            # Enter function scope
            self.scopes.append(('function', node.name))

            # Handle function arguments - store scope info to filter later
            for arg in node.args.args:
                if arg.arg == self.target_word:
                    self.definitions.append({
                        'line': node.lineno - 1,
                        'column': arg.col_offset if hasattr(arg, 'col_offset') else node.col_offset,
                        'type': 'argument',
                        'scope_depth': len(self.scopes),
                        'name': arg.arg,
                        'function_name': node.name,  # Track which function this arg belongs to
                        'function_line': node.lineno - 1
                    })

            # Handle *args and **kwargs
            if node.args.vararg and node.args.vararg.arg == self.target_word:
                self.definitions.append({
                    'line': node.lineno - 1,
                    'column': node.col_offset,
                    'type': 'vararg',
                    'scope_depth': len(self.scopes),
                    'name': node.args.vararg.arg,
                    'function_name': node.name,
                    'function_line': node.lineno - 1
                })

            if node.args.kwarg and node.args.kwarg.arg == self.target_word:
                self.definitions.append({
                    'line': node.lineno - 1,
                    'column': node.col_offset,
                    'type': 'kwarg',
                    'scope_depth': len(self.scopes),
                    'name': node.args.kwarg.arg,
                    'function_name': node.name,
                    'function_line': node.lineno - 1
                })

            # Visit function body
            for child in ast.iter_child_nodes(node):
                if child != node.args:  # Don't revisit args
                    self.visit_node(child)

            # Exit function scope
            self.scopes.pop()
            return

        # Class definitions
        elif isinstance(node, ast.ClassDef):
            self.add_definition(node, 'class')

            # Enter class scope
            self.scopes.append(('class', node.name))
            for child in ast.iter_child_nodes(node):
                self.visit_node(child)
            self.scopes.pop()
            return

        # Variable assignments
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                self.extract_names_from_target(target, 'variable', node)

        # Augmented assignments (+=, -=, etc.)
        elif isinstance(node, ast.AugAssign):
            self.extract_names_from_target(node.target, 'variable', node)

        # Annotated assignments (x: int = 5)
        elif isinstance(node, ast.AnnAssign):
            if node.target:
                self.extract_names_from_target(node.target, 'variable', node)

        # Import statements
        elif isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname or alias.name.split('.')[0]
                if name == self.target_word:
                    self.definitions.append({
                        'line': node.lineno - 1,
                        'column': node.col_offset,
                        'type': 'import',
                        'scope_depth': len(self.scopes),
                        'name': name
                    })

        # From imports
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                name = alias.asname or alias.name
                if name == self.target_word:
                    self.definitions.append({
                        'line': node.lineno - 1,
                        'column': node.col_offset,
                        'type': 'from_import',
                        'scope_depth': len(self.scopes),
                        'name': name
                    })

        # For loops
        elif isinstance(node, ast.For):
            self.extract_names_from_target(node.target, 'loop_variable', node)

        # With statements
        elif isinstance(node, ast.With):
            for item in node.items:
                if item.optional_vars:
                    self.extract_names_from_target(item.optional_vars, 'context_variable', node)

        # Exception handlers
        elif isinstance(node, ast.ExceptHandler):
            if node.name and node.name == self.target_word:
                self.definitions.append({
                    'line': node.lineno - 1,
                    'column': node.col_offset,
                    'type': 'exception_variable',
                    'scope_depth': len(self.scopes),
                    'name': node.name
                })

        # List/Dict/Set comprehensions
        elif isinstance(node, (ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp)):
            # Enter comprehension scope
            self.scopes.append(('comprehension', ''))
            for generator in node.generators:
                self.extract_names_from_target(generator.target, 'comprehension_variable', generator)
            for child in ast.iter_child_nodes(node):
                self.visit_node(child)
            self.scopes.pop()
            return

        # Continue traversing child nodes
        for child in ast.iter_child_nodes(node):
            self.visit_node(child)

    def extract_names_from_target(self, target, def_type, node):
        """Extract variable names from assignment targets (handles unpacking)"""
        if isinstance(target, ast.Name):
            if target.id == self.target_word:
                self.definitions.append({
                    'line': node.lineno - 1,
                    'column': target.col_offset,
                    'type': def_type,
                    'scope_depth': len(self.scopes),
                    'name': target.id
                })
        elif isinstance(target, (ast.Tuple, ast.List)):
            for elt in target.elts:
                self.extract_names_from_target(elt, def_type, node)
        elif isinstance(target, ast.Starred):
            self.extract_names_from_target(target.value, def_type, node)
        # Skip attribute assignments (obj.attr = value) and subscript assignments (obj[key] = value)
        # as these don't create new variable definitions


def get_addon_prefs(context):
    for addon_id in context.preferences.addons.keys():
        if 'textify' in addon_id.lower():
            return context.preferences.addons[addon_id].preferences
    return None


class TEXTIFY_OT_go_to_definition(bpy.types.Operator):
    bl_idname = "textify.go_to_definition"
    bl_label = "Go to Definition"
    bl_description = "Go to the definition of the selected word"

    @classmethod
    def poll(cls, context):
        prefs = get_addon_prefs(context)
        return (
            prefs and
            getattr(prefs, "enable_go_to_definition", False) and
            context.space_data and
            context.space_data.type == 'TEXT_EDITOR' and
            context.space_data.text
        )

    def get_word_at_cursor(self, text, line_index, char_index):
        if line_index >= len(text.lines):
            return None
        line = text.lines[line_index].body
        if char_index >= len(line):
            return None

        start = char_index
        end = char_index

        # Handle case where cursor is at the end of a word
        if char_index > 0 and not (line[char_index - 1].isalnum() or line[char_index - 1] == '_'):
            return None

        # Move start backwards
        while start > 0 and (line[start - 1].isalnum() or line[start - 1] == '_'):
            start -= 1

        # Move end forwards
        while end < len(line) and (line[end].isalnum() or line[end] == '_'):
            end += 1

        word = line[start:end]
        return word if word and word.isidentifier() else None

    def find_best_definition(self, definitions, current_line, source_lines):
        """Find the best definition based on scope and proximity"""
        if not definitions:
            return None

        # Filter out definitions that come after the current line (forward references)
        valid_definitions = [d for d in definitions if d['line'] <= current_line]

        if not valid_definitions:
            # If no definitions before current line, take the first one
            return definitions[0]

        # Filter out irrelevant function parameters
        filtered_definitions = []
        for d in valid_definitions:
            if d['type'] in ['argument', 'vararg', 'kwarg']:
                # Only include function parameters if the current line is within that function
                function_line = d.get('function_line', -1)
                if function_line >= 0:
                    # Find the end of the function by looking for the next function/class definition
                    function_end = len(source_lines)
                    for other_d in definitions:
                        if (other_d['type'] in ['function', 'async_function', 'class'] and
                                other_d['line'] > function_line):
                            function_end = other_d['line']
                            break

                    # Only include if current line is within the function
                    if function_line <= current_line < function_end:
                        filtered_definitions.append(d)
                else:
                    # If we can't determine function boundaries, skip it
                    continue
            else:
                # Include all non-parameter definitions
                filtered_definitions.append(d)

        if filtered_definitions:
            valid_definitions = filtered_definitions

        # Sort by line proximity (closest definition wins)
        valid_definitions.sort(key=lambda x: abs(current_line - x['line']))

        return valid_definitions[0]

    def jump_to_definition(self, text, definition):
        line_idx = definition['line']  # 0-based
        column = definition['column']

        if 0 <= line_idx < len(text.lines):
            bpy.ops.text.jump(line=line_idx + 1)  # Jump operator is 1-based
            line_body = text.lines[line_idx].body
            text.current_line_index = line_idx
            text.current_character = min(column, len(line_body))
            text.select_end_character = text.current_character
            return True
        return False

    def execute(self, context):
        text = context.space_data.text
        word = self.get_word_at_cursor(text, text.current_line_index, text.current_character)
        if not word:
            self.report({'INFO'}, "No valid identifier at cursor position")
            return {'CANCELLED'}

        source_code = text.as_string()
        finder = ASTDefinitionFinder(source_code, word)
        definitions = finder.find_definitions()

        if not definitions:
            self.report({'INFO'}, f"No definition found for '{word}'")
            return {'CANCELLED'}

        # Find the best definition based on current context
        source_lines = source_code.splitlines()
        best_definition = self.find_best_definition(definitions, text.current_line_index, source_lines)

        # Actually jump to the definition!
        if best_definition and self.jump_to_definition(text, best_definition):
            #self.report({'INFO'}, f"Jumped to definition of '{word}' at line {best_definition['line'] + 1}")
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, f"Could not jump to definition of '{word}'")
            return {'CANCELLED'}


def draw_go_to_menu(self, context):
    prefs = get_addon_prefs(context)
    space = context.space_data

    if not (
        prefs and
        getattr(prefs, "enable_go_to_definition", False) and
        space and
        space.type == 'TEXT_EDITOR' and
        space.text and
        space.text.current_line_index < len(space.text.lines)
    ):
        return

    text = space.text
    line_text = text.lines[text.current_line_index].body

    # Skip completely empty or whitespace-only lines
    if not line_text.strip():
        return

    layout = self.layout
    layout.operator("textify.go_to_definition")
    layout.separator()


classes = [TEXTIFY_OT_go_to_definition]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TEXT_MT_context_menu.prepend(draw_go_to_menu)


def unregister():
    bpy.types.TEXT_MT_context_menu.remove(draw_go_to_menu)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
