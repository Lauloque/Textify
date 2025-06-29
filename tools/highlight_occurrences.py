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
import blf
import re

from gpu import state
from gpu.shader import from_builtin
from gpu_extras.batch import batch_for_shader

from mathutils import Vector
from itertools import chain
from collections import deque

if bpy.app.version < (4, 0, 0):
    from bgl import glLineWidth, glEnable, glDisable, GL_BLEND

from bpy.props import BoolProperty


# --- Credits for Highlight Occurrences ---

# This highlighting functionality is based on the
# 'text_highlight_occurrences.py' script by K-410:
# https://github.com/K-410/blender-scripts/blob/master/2.8/text_highlight_occurrences.py
# Thank you, K-410, for this valuable contribution!

# --- End Credits ---


shader = from_builtin('UNIFORM_COLOR')
shader_uniform_float = shader.uniform_float
shader_bind = shader.bind
iterchain = chain.from_iterable
wrap_chars = {' ', '-'}
p = None


def get_addon_prefs(context):
    for addon_id in context.preferences.addons.keys():
        if 'textify' in addon_id.lower():
            return context.preferences.addons[addon_id].preferences
    return None


def draw_batches(context, batches, colors):
    prefs = get_addon_prefs(context)
    if bpy.app.version < (4, 0, 0):
        glLineWidth(p.line_thickness)
        shader_bind()
        glEnable(GL_BLEND)

        for draw, col in zip(batches, colors):
            shader_uniform_float("color", [*col])
            draw(shader)

        glDisable(GL_BLEND)

    else:
        shader_bind()
        state.blend_set("ALPHA")
        state.line_width_set(prefs.line_thickness)

        for draw, col in zip(batches, colors):
            shader_uniform_float("color", [*col])
            draw(shader)

        state.blend_set("NONE")


def make_whole_word_pattern(substr):
    safe = re.escape(substr)

    # If the substring is purely letters/numbers/underscores
    if all(c.isalnum() or c == '_' for c in substr):
        return r'\b{}\b'.format(safe)
    else:
        # If contains any special symbols like ( ) + * . -
        # Just match the exact escaped substring
        return safe


def get_matches(body, substr, selr=None):
    tho_props = bpy.context.scene.tho_settings
    matches = []
    append_matches = matches.append

    # Use whole word regex or just escape the string
    pattern = make_whole_word_pattern(
        substr) if tho_props.whole_word else re.escape(substr)
    flags = 0 if tho_props.case_sensitive else re.IGNORECASE

    exclude = set(range(*selr)) if selr else set()
    for m in re.finditer(pattern, body, flags):
        idx = m.start()
        span = m.end()

        # Skip if within selection
        if selr and (idx in exclude or span in exclude):
            continue

        append_matches(idx)

    return matches


def get_colors(draw_type):
    prefs = get_addon_prefs(bpy.context)
    colors = {
        'SCROLL': (prefs.col_scroll,),
        'SOLID': (prefs.col_bg,),
        'LINE': (prefs.col_line,),
        'FRAME': (prefs.col_line,),
        'SOLID_FRAME': (prefs.col_bg,
                        prefs.col_line)}
    return colors[draw_type]


def to_tris(line_height, pts, y_ofs):
    y1, y2 = Vector((0, y_ofs)), Vector((0, line_height))
    return (*iterchain(
        [(a, b, by, a, by, ay) for a, b, by, ay in
            [(a + y1, b + y1, b + y1 + y2, a + y1 + y2) for a, b, _ in pts]]),)


def to_scroll(line_height, pts, y_ofs):
    y1, y2 = Vector((-1, y_ofs)), Vector((0, y_ofs))
    return (*iterchain(
        [(a, b, by, a, by, ay) for a, b, by, ay in
            [(a + y1, b + y1, b + y1 + y2, a + y1 + y2) for a, b in pts]]),)


def to_lines(line_height, pts, y_ofs):
    y = Vector((0, y_ofs))
    return (*iterchain([(i + y, j + y) for i, j, _ in pts]),)


def to_frames(line_height, pts, y_ofs):
    y1, y2 = Vector((0, y_ofs)), Vector((0, line_height + y_ofs))
    return (*iterchain(
        [(a, b, ay, by + Vector((1, 0)), ay, a, by, b) for a, b, ay, by in
            [(a + y1, b + y1, a + y2, b + y2) for a, b, _ in pts]]),)


batch_types = {
    'SOLID': (('TRIS', to_tris),),
    'LINE': (('LINES', to_lines),),
    'FRAME': (('LINES', to_frames),),
    'SOLID_FRAME': (('TRIS', to_tris),
                    ('LINES', to_frames))}


# for calculating offsets and max displayable characters
# source/blender/windowmanager/intern/wm_window.c$515
def get_widget_unit(context):
    ui_scale = context.preferences.view.ui_scale
    padding_px = 10  # Blender UI padding (rough guess)
    return int(2 * (padding_px * ui_scale))


# Character Width and X Offset Calculation
def get_char_width_and_offset(loc, show_line_numbers, lenl):
    cw = loc(0, 1)[0] - loc(0, 0)[0]
    x_offset = cw
    if show_line_numbers:
        x_offset += cw * (len(repr(lenl)) + 2)
    return cw, x_offset


# Maximum displayable characters in editor
def get_char_max(rw, wunits, x_offset, cw):
    usable_width = rw - wunits - x_offset
    char_max = int(usable_width // cw)
    return max(char_max, 8)


# Calculate true top and pixel span when blender's show_word_wrap enabled
def calc_top(lines, maxy, line_height, rh, y_offset, char_max):
    top = 0
    found = False
    wrap_offset = maxy + y_offset
    wrap_span_px = -line_height
    for idx, line in enumerate(lines):
        wrap_span_px += line_height
        if wrap_offset < rh:
            if not found:
                found = True
                top = idx
        wrap_offset -= line_height
        pos = start = 0
        end = char_max

        body = line.body
        if len(body) < char_max:
            continue

        for c in body:
            if pos - start >= char_max:
                wrap_span_px += line_height
                if wrap_offset < rh:
                    if not found:
                        found = True
                        top = idx
                wrap_offset -= line_height
                start = end
                end += char_max
            elif c == " " or c == "-":
                end = pos + 1
            pos += 1
    return top, wrap_span_px


# Find all occurrences and generate points to draw rects if blender's show_word_wrap enabled
def get_wrapped_pts(context, substr, selr, line_height, wunits, rh, rw):
    tho_props = context.scene.tho_settings

    pts = []
    # because we want to draw selected text with custom color
    scrollpts = [[], []]
    append_pts = pts.append

    st = context.space_data
    txt = st.text
    lines = txt.lines
    curl = txt.current_line
    strlen = len(substr)
    lenl = len(lines)
    loc = st.region_location_from_cursor

    # Find character width and offset
    cw, x_offset = get_char_width_and_offset(loc, st.show_line_numbers, lenl)

    # Maximum displayable characters in editor
    char_max = get_char_max(rw, wunits, x_offset, cw)

    # Vertical span in pixels
    firstxy = loc(0, 0)
    y_offset = line_height * 0.2
    top, vspan_px = calc_top(
        lines, firstxy[1], line_height, rh, y_offset, char_max)

    # Screen coord tables for fast lookup of match positions
    x_table = range(0, cw * char_max, cw)
    y_top = loc(top, 0)[1]
    y_table = range(y_top, y_top - vspan_px, -line_height)
    y_table_size = len(y_table)

    wrap_total = w_count = wrap_offset = 0

    # Generate points for scrollbar highlights
    # if p.show_in_scroll:
    if tho_props.show_in_scroll:
        args = st, substr, wunits, vspan_px, rw, rh, line_height
        scrollpts = scrollpts_get(*args)

    # Generate points for text highlights
    for l_idx, line in enumerate(lines[top:top + st.visible_lines + 4], top):
        body = line.body
        if line == curl:
            # Selected line is processed separately
            match_indices = get_matches(body, substr, selr)
        else:
            match_indices = get_matches(body, substr)

        # Hard max for match finding
        if len(match_indices) > 1000:
            return pts, scrollpts

        # Wraps
        w_list = []
        w_start = 0
        w_end = char_max
        w_count = -1
        coords = deque()
        append_w_list = w_list.append

        # Simulate word wrapping for displayed text and store
        # local text coordinates and wrap indices for each line.
        for idx, char in enumerate(body):
            if idx - w_start >= char_max:
                append_w_list(body[w_start:w_end])
                w_count += 1
                coords.extend([(i, w_count) for i in range(w_end - w_start)])
                w_start = w_end
                w_end += char_max
            elif char in wrap_chars:
                w_end = idx + 1

        append_w_list(body[w_start:])
        w_end = w_start + (len(body) - w_start)
        w_count += 1
        coords.extend([(i, w_count) for i in range(w_end - w_start)])
        w_indices = [i for i, _ in enumerate(w_list) for _ in _]

        # ==== Case if 1 wrapped line ====
        # Ensure y_table is long enough to include all wrapped rows
        if coords and lenl == 1:
            max_w_line = max(w_line for _, w_line in coords)
            if max_w_line >= y_table_size:
                last_y = y_table[-1] if y_table else y_top
                extra = [last_y - line_height *
                         (i + 1) for i in range(max_w_line - y_table_size + 1)]
                y_table = list(y_table) + extra
                # Some weird behavior if one row in wrapped line
                if y_top not in y_table:
                    y_table = [y_top]
                y_table_size = len(y_table)

        # screen coords for wrapped char/line by match index
        for match_idx in match_indices:
            mspan = match_idx + strlen

            w_char, w_line = coords[match_idx]
            w_char_end, w_line_end = coords[mspan - 1]

            # in edge cases where a single wrapped line has
            # several thousands of matches, skip and continue
            if w_line > y_table_size or w_line_end > y_table_size:
                continue

            matchy = y_table[w_line] - wrap_offset
            if matchy > rh or matchy < -line_height:
                continue

            co_1 = Vector((x_offset + x_table[w_char], matchy))

            if w_line != w_line_end:
                start = match_idx
                end = wrap_idx = 0

                for midx in range(strlen):
                    widx = match_idx + midx
                    w_char, w_line = coords[widx]
                    matchy = y_table[w_line] - wrap_offset

                    if matchy != co_1.y:
                        co_2 = Vector((x_table[w_char - 1] + cw + x_offset,
                                       y_table[w_line - 1] - wrap_offset))

                        if wrap_idx:
                            text = w_list[w_indices[widx - 1]]
                        else:
                            text = body[start:widx]
                        append_pts((co_1, co_2, text))
                        co_1 = Vector((x_offset + x_table[w_char], matchy))
                        end = midx
                        start += end
                        wrap_idx += 1
                        continue

                text = body[match_idx:mspan][end:]
                co_2 = Vector((x_offset + x_table[w_char] + cw, matchy))
                append_pts((co_1, co_2, text))

            else:
                text = body[match_idx:mspan]
                co_2 = co_1.copy()
                co_2.x += cw * strlen
                append_pts((co_1, co_2, text))

        wrap_total += w_count + 1
        wrap_offset = line_height * wrap_total

    return pts, scrollpts


# Find all occurrences and generate points to draw rects if blender's show_word_wrap disabled
def get_non_wrapped_pts(context, substr, selr, line_height, wunits, rh, rw):
    tho_props = context.scene.tho_settings
    pts = []
    # because we want to draw selected text with custom color
    scrollpts = [[], []]
    append_pts = pts.append

    st = context.space_data
    txt = st.text
    top = st.top
    lines = txt.lines
    curl = txt.current_line
    strlen = len(substr)
    lenl = len(lines)
    loc = st.region_location_from_cursor

    # Find character width and offset
    cw, x_offset = get_char_width_and_offset(loc, st.show_line_numbers, lenl)

    # Vertical span in pixels
    firstxy = loc(0, 0)
    vspan_px = line_height
    if lenl > 1:
        vspan_px = abs(firstxy[1] - loc(lenl - 1, len(lines[-1].body))[1])

    hor_max_px = rw - (wunits // 2)
    str_span_px = cw * strlen

    # Generate points for scrollbar highlights
    if tho_props.show_in_scroll:
        args = st, substr, wunits, vspan_px, rw, rh, line_height
        scrollpts = scrollpts_get(*args)

    # Generate points for text highlights
    for idx, line in enumerate(lines[top:top + st.visible_lines + 2], top):
        body = line.body
        if line == curl:
            match_indices = get_matches(body, substr, selr)
        else:
            match_indices = get_matches(body, substr)

        if len(match_indices) > 1000:
            return pts, scrollpts

        for match_idx in match_indices:
            x1, y1 = loc(idx, match_idx)
            x2 = x1 + str_span_px

            # Skip matches outside horizontal view
            if x1 > hor_max_px or x2 <= x_offset:
                continue

            # Clip text to visible part
            char_offset = (x_offset - x1) // cw if x1 < x_offset else 0
            end_idx = match_idx + strlen
            end_idx -= 1 + (x2 - hor_max_px) // cw if x2 > hor_max_px else 0

            append_pts((Vector((x1 + cw * char_offset, y1)),
                        Vector((x2, y1)),
                        body[match_idx + char_offset:end_idx]))

    return pts, scrollpts


# Calc rows in wrapped stroke
def line_wrap_rows(body, char_max):
    if len(body) <= char_max:
        return 1

    rows = 1
    start = 0
    end = char_max

    for i, c in enumerate(body):
        if i - start >= char_max:
            rows += 1
            start = end
            end += char_max
        elif c in wrap_chars:
            end = i + 1

    return rows


def wrap_coords_and_row(body, char_max, selected_char_index=None):
    coords = {}
    wrap_row = 0
    start = 0
    end = char_max
    selected_row = None

    for idx, c in enumerate(body):
        coords[idx] = wrap_row

        if selected_char_index is not None and idx == selected_char_index:
            selected_row = wrap_row
            return coords, selected_row

        if idx - start >= char_max:
            wrap_row += 1
            start = end
            end += char_max
        elif c in wrap_chars:
            end = idx + 1

    return coords, selected_row


def scrollpts_get(st, substr, wunits, vspan_px, rw, rh, line_height):
    ui_scale = bpy.context.preferences.view.ui_scale
    prefs = get_addon_prefs(bpy.context)

    scrollpts = []
    selectedpts = []
    append_scrollpts = scrollpts.append
    append_selected = selectedpts.append

    txt = st.text
    lines = txt.lines
    curl = txt.current_line
    lenl = len(lines)
    loc = st.region_location_from_cursor

    # Determine visual line index per logical line
    visual_indices = []
    total_lines = 0
    append_vis = visual_indices.append

    if st.show_word_wrap:
        # Find character width and offset
        cw, x_offset = get_char_width_and_offset(
            loc, st.show_line_numbers, lenl)

        # Maximum displayable characters in editor
        char_max = get_char_max(rw, wunits, x_offset, cw)

        for line in lines:
            append_vis(total_lines)
            total_lines += line_wrap_rows(line.body, char_max)
    else:
        visual_indices = list(range(lenl))
        total_lines = lenl

    if total_lines == 0:
        return scrollpts, selectedpts

    # x offset for scrollbar widget start
    wrh_org = (vspan_px // line_height) + 1
    vispan = st.top + st.visible_lines
    blank_lines = st.visible_lines // 2
    if wrh_org + blank_lines < vispan:
        blank_lines = vispan - wrh_org
    wrh = wrh_org + blank_lines

    top_margin = 20 * ui_scale
    bottom_margin = 0
    pixels_available = rh - (top_margin + bottom_margin)
    scrolltop = rh - top_margin

    # Horizontal scrollbar position
    sx_1 = rw - (prefs.scroll_horiz_pos + 4 * ui_scale)
    sx_2 = sx_1 - prefs.scroll_marker_length * ui_scale

    # Vertical spacing per visual line
    j = wrh_org / total_lines * pixels_available

    # Place scroll markers (all wrapped lines markers are distributed across the scrollbar)
    for i, line in enumerate(lines):
        body = line.body
        match_indices = get_matches(body, substr)
        if not match_indices:
            continue

        if st.show_word_wrap:
            coords, _ = wrap_coords_and_row(body, char_max)
            added_rows = set()
            for idx in match_indices:
                row = coords.get(idx, 0)
                if row not in added_rows:
                    visual_line_idx = visual_indices[i] + row
                    y = scrolltop - (visual_line_idx * j) / wrh
                    append_scrollpts((Vector((sx_1, y)), Vector((sx_2, y))))
                    added_rows.add(row)
        else:
            visual_line_idx = visual_indices[i]
            y = scrolltop - (visual_line_idx * j) / wrh
            append_scrollpts((Vector((sx_1, y)), Vector((sx_2, y))))

    # Selected line marker (wrapped support)
    selected_idx = lines[:].index(curl)

    # Calculate character position of selected word
    selr = sorted((txt.current_character, txt.select_end_character))
    substr_len = selr[1] - selr[0]
    if substr_len > 0:
        if st.show_word_wrap:
            # Determine which wrapped row contains the selected character
            coords, selected_wrap_row = wrap_coords_and_row(
                curl.body, char_max, selr[0])
            visual_line_idx = visual_indices[selected_idx] + selected_wrap_row
        else:
            visual_line_idx = visual_indices[selected_idx]

        y_cursor = scrolltop - (visual_line_idx * j) / wrh
        append_selected((Vector((sx_1, y_cursor)), Vector((sx_2, y_cursor))))

    return scrollpts, selectedpts


def get_theme_selected_color(context):
    theme_color = context.preferences.themes.items()[
        0][1].text_editor.selected_text
    # Convert Color (r, g, b) to (r, g, b, a)
    return (theme_color.r, theme_color.g, theme_color.b, 1.0)


def draw_highlights(context):
    st = context.space_data
    txt = st.text
    prefs = get_addon_prefs(context)

    if not prefs.enable_highlight_occurrences or not txt:
        return  # Ensure text is available

    # Only proceed if current line exists
    if not txt.current_line:
        return

    try:
        selr = sorted((txt.current_character, txt.select_end_character))
    except AttributeError:
        return  # Handle case where text data isn't properly initialized

    curl = txt.current_line

    highlight_mode = prefs.highlight_mode

    if highlight_mode == 'AUTO':
        if st.find_text and st.find_text.strip():
            substr = st.find_text
        else:
            substr = curl.body[slice(*selr)]
    elif highlight_mode == 'SELECTION':
        substr = curl.body[slice(*selr)]
    elif highlight_mode == 'FIND_TEXT':
        substr = st.find_text

    if not substr.strip():
        # Nothing to find
        return
    if len(substr) >= prefs.min_str_len and curl == txt.select_end_line:
        wunits = get_widget_unit(context)

        # Case if only one line in text and word wrap on/off
        lines = txt.lines
        lenl = len(lines)
        loc = st.region_location_from_cursor

        region = context.region
        rh, rw = region.height, region.width

        if lenl != 1:
            line_height = loc(0, 0)[1] - loc(1, 0)[1]

            # if blender's show_word_wrap enabled
            if st.show_word_wrap:
                # Find character width and offset
                cw, x_offset = get_char_width_and_offset(
                    loc, st.show_line_numbers, lenl)

                # Maximum displayable characters in editor
                char_max = get_char_max(rw, wunits, x_offset, cw)

                # How many rows in first line to get proper line height
                line_rows = line_wrap_rows(lines[0].body, char_max)
                if line_rows > 1:
                    line_height = line_height // line_rows

        else:
            line_height_dpi = (wunits * st.font_size) / 20
            line_height = int(line_height_dpi + 0.3 * line_height_dpi)

            # if blender's show_word_wrap enabled
            if st.show_word_wrap:
                # Find character width and offset
                cw, x_offset = get_char_width_and_offset(
                    loc, st.show_line_numbers, lenl)

                # Maximum displayable characters in editor
                char_max = get_char_max(rw, wunits, x_offset, cw)

                # How many rows in first line to get proper line height
                line_rows = line_wrap_rows(lines[0].body, char_max)

                if line_rows > 1:
                    # Estimate height per wrapped row
                    full_height = loc(0, 0)[1]  # top of the line
                    baseline = loc(0, len(lines[0].body))[1]
                    line_height = (full_height - baseline) // (line_rows - 1)

                if line_height <= 0:
                    line_height_dpi = (wunits * st.font_size) / 20
                    line_height = int(line_height_dpi + 0.3 * line_height_dpi)

        # if blender's show_word_wrap enabled/disabled
        args = context, substr, selr, line_height, wunits, rh, rw
        if st.show_word_wrap:
            pts, (scrollpts, scrollpts_selected) = get_wrapped_pts(*args)
        else:
            pts, (scrollpts, scrollpts_selected) = get_non_wrapped_pts(*args)

        # ===== Scrollbar marker drawing  =====
        # shapes type
        scroll_tris = to_scroll(line_height, scrollpts, 2)
        scroll_tris_selected = to_scroll(line_height, scrollpts_selected, 2)

        # shapes color
        scroll_color_normal = prefs.col_scroll
        if prefs.col_preset == 'CUSTOM':
            scroll_color_selected = prefs.col_scroll_selected
        else:
            scroll_color_selected = get_theme_selected_color(context)

        # shapes batch
        scroll_batch = [(scroll_tris, scroll_color_normal),
                        (scroll_tris_selected, scroll_color_selected)]
        for tris, color in scroll_batch:
            batch = batch_for_shader(shader, 'TRIS', {'pos': tris})
            draw_batches(context, [batch.draw], [color])

        # =====  Text words selection drawing =====
        y_offset = 0
        draw_type = prefs.draw_type
        batches = [batch_for_shader(
                   shader, btyp, {'pos': fn(line_height, pts, y_offset)}).draw
                   for b in batch_types[draw_type] for (btyp, fn) in [b]]
        draw_batches(context, batches, get_colors(draw_type))

        # ===== Calculate proper font_size based on the UI scale =====
        font_id = 1

        # Manual compensation for some weird font scale behaviour
        ui_scale = context.preferences.view.ui_scale
        # <=== Need to find better solution?
        font_size = int(st.font_size * ui_scale)
        list_size = [6, 8, 9,
                     11, 13, 16, 18,
                     21, 23, 26, 28,
                     31, 33, 36, 38,
                     41, 43, 46, 48, 49,
                     51, 53, 54, 56, 58, 59,
                     61, 63, 64, 66, 68, 69]
        if ui_scale == 1 and font_size in list_size:
            font_size -= 1

        # Add compensation for custom UI scale in some uncalculated values if needed
        font_size = font_size + prefs.font_size_comp

        # Highlight font overlay starts here
        y_offset += line_height * 0.2  # found a value, but why 0.2?
        blf.color(font_id, *prefs.fg_col)
        blf.size(font_id, font_size)
        for co, _, substring in pts:
            co.y += y_offset
            blf.position(font_id, *co, 0)
            blf.draw(font_id, substring)


def redraw(context):
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'TEXT_EDITOR':
                area.tag_redraw()


def _disable(context, st, prefs):
    handle = getattr(prefs, "_handle", None)
    if handle:
        st.draw_handler_remove(handle, 'WINDOW')
        redraw(context)
        del prefs._handle


def update_colors(self, context):
    col_attrs = ("col_bg", "fg_col", "col_line", 'col_scroll')
    if self.col_preset != 'CUSTOM':
        for source, target in zip(self.colors[self.col_preset], col_attrs):
            setattr(self, target, source)


def update_highlight(self, context):
    prefs = get_addon_prefs(context)
    st = bpy.types.SpaceTextEditor
    _disable(context, st, prefs)
    if not self.enable_highlight_occurrences:
        return

    args = draw_highlights, (context,), 'WINDOW', 'POST_PIXEL'
    bpy.app.timers.register(lambda: setattr(prefs, "_handle",
                            st.draw_handler_add(*args)), first_interval=0)


class HIGHLIGHT_OCCURRENCES_PG_settings(bpy.types.PropertyGroup):
    show_in_scroll: BoolProperty(
        description="Show in scrollbar",
        name="Show in Scrollbar",
        default=True
    )

    case_sensitive: BoolProperty(
        description='Case Sensitive Matching',
        name='Case Sensitive',
        default=False
    )

    whole_word: BoolProperty(
        description="Search for whole word only. With some tweaks",
        name="Whole Word +",
        default=False,
        # update=update_highlight
    )


def register():
    bpy.utils.register_class(HIGHLIGHT_OCCURRENCES_PG_settings)

    bpy.types.Scene.tho_settings = bpy.props.PointerProperty(
        type=HIGHLIGHT_OCCURRENCES_PG_settings)


def unregister():
    bpy.utils.unregister_class(HIGHLIGHT_OCCURRENCES_PG_settings)
    redraw(getattr(bpy, "context"))

    del bpy.types.Scene.tho_settings
