##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
##### END GPL LICENSE BLOCK #####


import bpy
import re
from gpu import state
from gpu.shader import from_builtin
from gpu_extras.batch import batch_for_shader
from mathutils import Vector
import blf


# Portions of this code adapted from: https://github.com/K-410/blender-scripts/blob/master/2.8/text_highlight_occurrences.py
# Original author: K-410


shader = from_builtin('UNIFORM_COLOR')
shader_uniform_float = shader.uniform_float
shader_bind = shader.bind


def get_addon_prefs(context):
    for addon_id in context.preferences.addons.keys():
        if 'textify' in addon_id.lower():
            return context.preferences.addons[addon_id].preferences
    return None


def draw_batches(context, batches, colors):
    shader_bind()
    state.blend_set("ALPHA")
    state.line_width_set(2)
    for draw, col in zip(batches, colors):
        shader_uniform_float("color", [*col])
        draw(shader)
    state.blend_set("NONE")


def get_matches(text, substr, case_sensitive=False, exclude_range=None):
    matches = []
    flags = 0 if case_sensitive else re.IGNORECASE
    pattern = re.escape(substr)
    exclude = set(range(*exclude_range)) if exclude_range else set()

    for match in re.finditer(pattern, text, flags):
        start_idx = match.start()
        end_idx = match.end()
        if exclude_range and (start_idx in exclude or end_idx in exclude):
            continue
        matches.append(start_idx)
    return matches


def get_scrollbar_markers(context, substr, selection_range):
    st = context.space_data
    txt = st.text
    if not txt:
        return [], []

    prefs = get_addon_prefs(context)
    ui_scale = context.preferences.view.ui_scale
    region = context.region
    rh = region.height
    rw = region.width

    lines = txt.lines
    current_line = txt.current_line
    lenl = len(lines)

    if lenl == 0:
        return [], []

    top_margin = 20 * ui_scale
    bottom_margin = 0
    pixels_available = rh - (top_margin + bottom_margin)
    scrolltop = rh - top_margin

    sx_1 = rw - (prefs.scroll_horiz_pos + 5 * ui_scale)
    sx_2 = sx_1 - prefs.scroll_marker_length * ui_scale

    j = pixels_available / lenl if lenl > 0 else 0

    scrollpts = []
    selected_scrollpts = []

    for line_idx, line in enumerate(lines):
        body = line.body
        if line == current_line:
            matches = get_matches(
                body, substr, prefs.case_sensitive, selection_range)
        else:
            matches = get_matches(body, substr, prefs.case_sensitive)

        if matches:
            y = scrolltop - (line_idx * j)
            marker_start = Vector((sx_1, y))
            marker_end = Vector((sx_2, y))

            if line == current_line and selection_range:
                selected_scrollpts.append((marker_start, marker_end))
            else:
                scrollpts.append((marker_start, marker_end))

    return scrollpts, selected_scrollpts


def get_highlight_points(context, substr, selection_range):
    st = context.space_data
    txt = st.text
    if not txt:
        return []

    prefs = get_addon_prefs(context)
    points = []
    lines = txt.lines
    current_line = txt.current_line
    substr_len = len(substr)
    region = context.region
    top_line = st.top
    visible_lines = st.visible_lines

    for line_idx in range(top_line, min(top_line + visible_lines + 2, len(lines))):
        line = lines[line_idx]
        body = line.body
        if line == current_line:
            matches = get_matches(
                body, substr, prefs.case_sensitive, selection_range)
        else:
            matches = get_matches(body, substr, prefs.case_sensitive)

        for match_idx in matches:
            try:
                x1, y1 = st.region_location_from_cursor(line_idx, match_idx)
                x2, y2 = st.region_location_from_cursor(
                    line_idx, match_idx + substr_len)
                if (x1 < 0 or x1 > region.width or y1 < 0 or y1 > region.height):
                    continue
                pt1 = Vector((x1, y1))
                pt2 = Vector((x2, y1))
                match_text = body[match_idx:match_idx + substr_len]
                points.append((pt1, pt2, match_text))
            except:
                continue
    return points


def to_triangles(points, line_height):
    triangles = []
    y_offset = line_height * 0.0
    for pt1, pt2, _ in points:
        bottom_left = Vector((pt1.x, pt1.y - y_offset))
        bottom_right = Vector((pt2.x, pt1.y - y_offset))
        top_left = Vector((pt1.x, pt1.y + line_height - y_offset))
        top_right = Vector((pt2.x, pt1.y + line_height - y_offset))
        triangles.extend([bottom_left, bottom_right, top_left])
        triangles.extend([bottom_right, top_right, top_left])
    return triangles


def to_scroll_triangles(scroll_points, line_height):
    triangles = []
    marker_height = 2

    for pt1, pt2 in scroll_points:
        bottom_left = Vector((pt2.x, pt1.y - marker_height / 2))
        bottom_right = Vector((pt1.x, pt1.y - marker_height / 2))
        top_left = Vector((pt2.x, pt1.y + marker_height / 2))
        top_right = Vector((pt1.x, pt1.y + marker_height / 2))

        triangles.extend([bottom_left, bottom_right, top_left])
        triangles.extend([bottom_right, top_right, top_left])

    return triangles


def get_theme_selected_color(context):
    try:
        theme_color = context.preferences.themes.items()[
            0][1].text_editor.selected_text
        return (theme_color.r, theme_color.g, theme_color.b, 1.0)
    except:
        return (1.0, 0.5, 0.0, 1.0)


def draw_text_highlights(context, points, line_height):
    if not points:
        return

    prefs = get_addon_prefs(context)
    st = context.space_data

    triangles = to_triangles(points, line_height)
    if triangles:
        batch = batch_for_shader(shader, 'TRIS', {'pos': triangles})
        draw_batches(context, [batch.draw], [prefs.highlight_color])

    font_id = 1
    ui_scale = context.preferences.view.ui_scale
    font_size = int(st.font_size * ui_scale)
    blf.size(font_id, font_size)
    blf.color(font_id, *prefs.text_color)
    y_offset = line_height * 0.2
    for pt1, _, text in points:
        blf.position(font_id, pt1.x, pt1.y + y_offset, 0)
        blf.draw(font_id, text)


def draw_scrollbar_markers(context, scrollpts, selected_scrollpts, line_height):
    prefs = get_addon_prefs(context)

    if not prefs.show_in_scroll:
        return

    if scrollpts:
        scroll_triangles = to_scroll_triangles(scrollpts, line_height)
        if scroll_triangles:
            batch = batch_for_shader(shader, 'TRIS', {'pos': scroll_triangles})
            draw_batches(context, [batch.draw], [prefs.scroll_color])

    if selected_scrollpts:
        selected_scroll_triangles = to_scroll_triangles(
            selected_scrollpts, line_height)
        if selected_scroll_triangles:
            batch = batch_for_shader(
                shader, 'TRIS', {'pos': selected_scroll_triangles})
            selected_color = get_theme_selected_color(context)
            draw_batches(context, [batch.draw], [selected_color])


def draw_highlights(context):
    st = context.space_data
    txt = st.text
    if not txt:
        return
    prefs = get_addon_prefs(context)

    if not getattr(prefs, "enable_highlight_occurrences", False) or not txt:
        return  # Ensure text is available

    # Only proceed if current line exists
    if not txt.current_line:
        return

    selection_range = sorted((txt.current_character, txt.select_end_character))
    current_line = txt.current_line

    highlight_mode = prefs.highlight_mode

    if highlight_mode == 'AUTO':
        if st.find_text and st.find_text.strip():
            selected_text = st.find_text
        else:
            selected_text = current_line.body[slice(*selection_range)]
    elif highlight_mode == 'SELECTION':
        selected_text = current_line.body[slice(*selection_range)]
    elif highlight_mode == 'FIND_TEXT':
        selected_text = st.find_text

    if not selected_text.strip() or len(selected_text) < 2:
        return
    if current_line != txt.select_end_line:
        return

    points = get_highlight_points(context, selected_text, selection_range)
    scrollpts, selected_scrollpts = get_scrollbar_markers(
        context, selected_text, selection_range)

    try:
        if len(txt.lines) > 1:
            loc = st.region_location_from_cursor
            y1 = loc(0, 0)[1]
            y2 = loc(1, 0)[1]
            line_height = abs(y1 - y2)
        else:
            line_height = int(st.font_size * 1.5)
    except:
        line_height = 20
    if line_height < 10:
        line_height = 20

    draw_scrollbar_markers(context, scrollpts, selected_scrollpts, line_height)
    draw_text_highlights(context, points, line_height)


def redraw_text_editors(context):
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'TEXT_EDITOR':
                area.tag_redraw()


def update_highlight(self, context):
    st = bpy.types.SpaceTextEditor

    if hasattr(st, "_highlight_handle"):
        st.draw_handler_remove(st._highlight_handle, 'WINDOW')
        delattr(st, "_highlight_handle")

    if self.enable_highlight_occurrences:
        def add_handler():
            st._highlight_handle = st.draw_handler_add(
                draw_highlights, (bpy.context,), 'WINDOW', 'POST_PIXEL')
            redraw_text_editors(bpy.context)
            return None

        bpy.app.timers.register(add_handler, first_interval=0.1)


def register():
    prefs = get_addon_prefs(bpy.context)
    if prefs.enable_highlight_occurrences:
        update_highlight(prefs, bpy.context)


def unregister():
    prefs = get_addon_prefs(bpy.context)
    prefs.enable_highlight_occurrences = False

    st = bpy.types.SpaceTextEditor
    if hasattr(st, "_highlight_handle"):
        st.draw_handler_remove(st._highlight_handle, 'WINDOW')
        delattr(st, "_highlight_handle")
        redraw_text_editors(bpy.context)
