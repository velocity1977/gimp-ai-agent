#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GIMP Agentic AI Plugin for GIMP 3.2.4 (Windows / Cross-platform)
Implements a persistent, main-thread-safe socket server on localhost:9877
Exposes atomic dispatch handlers for agentic control.
"""

import gi
gi.require_version('Gimp', '3.0')
gi.require_version('GimpUi', '3.0')
gi.require_version('Gegl', '0.4')

from gi.repository import Gimp, GimpUi, GLib, GObject, Gio, Gegl

import os
import sys
import json
import socket
import threading
import traceback
import math

DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 9877
DEFAULT_TIMEOUT_SECONDS = 30.0

def N_(message): return message
def _(message): return GLib.dgettext(None, message)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. HELPER UTILITIES: Colors, State Grounding, Thread Dispatching
# ═══════════════════════════════════════════════════════════════════════════════

def parse_color_to_gegl(color_val):
    """
    Centralized color parser for GIMP 3.x / GEGL.
    Accepts:
      - Hex string: "#FF5500", "#FFF"
      - CSS / Name string: "red", "blue", "rgb(1.0, 0.5, 0.0)", "rgba(255, 0, 0, 1.0)"
      - Array/Tuple: [1.0, 0.0, 0.0, 1.0] (0-1 float) or [255, 0, 0] (0-255 int)
    Returns a Gegl.Color object.
    """
    if color_val is None:
        return Gegl.Color.new("black")
    
    if isinstance(color_val, str):
        c_str = color_val.strip()
        if c_str.startswith("#"):
            # Hex color
            hex_body = c_str.lstrip("#")
            if len(hex_body) == 3:
                r = int(hex_body[0] + hex_body[0], 16) / 255.0
                g = int(hex_body[1] + hex_body[1], 16) / 255.0
                b = int(hex_body[2] + hex_body[2], 16) / 255.0
                return Gegl.Color.new(f"rgb({r:.4f}, {g:.4f}, {b:.4f})")
            elif len(hex_body) in (6, 8):
                r = int(hex_body[0:2], 16) / 255.0
                g = int(hex_body[2:4], 16) / 255.0
                b = int(hex_body[4:6], 16) / 255.0
                a = int(hex_body[6:8], 16) / 255.0 if len(hex_body) == 8 else 1.0
                return Gegl.Color.new(f"rgba({r:.4f}, {g:.4f}, {b:.4f}, {a:.4f})")
        # Try standard name / format directly
        return Gegl.Color.new(c_str)
    
    if isinstance(color_val, (list, tuple)):
        if len(color_val) >= 3:
            # Check if 0-255 or 0-1
            is_255 = any(x > 1.0 for x in color_val[:3])
            r = color_val[0] / 255.0 if is_255 else float(color_val[0])
            g = color_val[1] / 255.0 if is_255 else float(color_val[1])
            b = color_val[2] / 255.0 if is_255 else float(color_val[2])
            a = 1.0
            if len(color_val) >= 4:
                a = color_val[3] / 255.0 if (is_255 and color_val[3] > 1.0) else float(color_val[3])
            return Gegl.Color.new(f"rgba({r:.4f}, {g:.4f}, {b:.4f}, {a:.4f})")
            
    return Gegl.Color.new("black")


def get_image_by_id(image_id):
    """Resolve an image object by image_id or default to the active/first image."""
    images = Gimp.get_images()
    if not images:
        return None
    if image_id is None:
        if len(images) > 1:
            raise ValueError("Multiple images open. You must provide an 'image_id' parameter.")
        return images[0]
    for img in images:
        if img.get_id() == int(image_id):
            return img
    return None


def get_layer_by_id(image, layer_id):
    """Resolve a layer in the given image by layer_id or default to active layer."""
    if image is None:
        return None
    layers = image.get_layers()
    if not layers:
        return None
    if layer_id is None:
        # Get active layer or first layer
        selected = image.get_selected_layers()
        if selected:
            return selected[0]
        return layers[0]
    for lyr in layers:
        if lyr.get_id() == int(layer_id):
            return lyr
    return None


def build_image_state(image=None):
    """
    Builds the standardized image state dictionary returned with every tool call.
    Includes canvas dimensions, active layer, layer list, and file path.
    """
    if image is None:
        images = Gimp.get_images()
        if images:
            image = images[0]
            
    if image is None:
        return {
            "has_open_image": False,
            "images_count": 0,
            "image_id": None,
            "width": 0,
            "height": 0,
            "layers": [],
            "active_layer_id": None,
            "active_layer_name": None,
            "file_path": None
        }

    layers_info = []
    for lyr in image.get_layers():
        layers_info.append({
            "layer_id": lyr.get_id(),
            "name": lyr.get_name(),
            "visible": lyr.get_visible(),
            "opacity": lyr.get_opacity(),
            "width": lyr.get_width(),
            "height": lyr.get_height()
        })

    selected_layers = image.get_selected_layers()
    active_layer = selected_layers[0] if selected_layers else (image.get_layers()[0] if image.get_layers() else None)
    
    file_obj = image.get_file()
    file_path = file_obj.get_path() if file_obj else None

    return {
        "has_open_image": True,
        "images_count": len(Gimp.get_images()),
        "image_id": image.get_id(),
        "width": image.get_width(),
        "height": image.get_height(),
        "precision": str(image.get_precision()),
        "base_type": str(image.get_base_type()),
        "layers_count": len(layers_info),
        "layers": layers_info,
        "active_layer_id": active_layer.get_id() if active_layer else None,
        "active_layer_name": active_layer.get_name() if active_layer else None,
        "file_path": file_path
    }


def make_success_response(data, image=None):
    """Standardized success response wrapper."""
    return {
        "status": "success",
        "data": data,
        "image_state": build_image_state(image)
    }


def make_error_response(error_type, message, image=None):
    """Standardized error response wrapper with live image state."""
    return {
        "status": "error",
        "error_type": error_type,
        "message": message,
        "image_state": build_image_state(image)
    }


def _get_layer_offsets(layer):
    """
    Safely retrieve a layer's (x, y) canvas offsets in GIMP 3.x.

    `Gimp.Item.get_offsets()` returns a 3-tuple `(success_bool, x_int, y_int)` via
    GI out-parameters. We unpack properly here rather than relying on index access,
    which breaks silently when the binding returns a different container type.
    Falls back to the PDB procedure if the GI method fails.
    """
    try:
        ret = layer.get_offsets()
        # GI binding returns (bool, int, int)
        if isinstance(ret, (list, tuple)) and len(ret) >= 3:
            return int(ret[1]), int(ret[2])
        # Some GI builds return just (x, y)
        if isinstance(ret, (list, tuple)) and len(ret) == 2:
            return int(ret[0]), int(ret[1])
    except Exception:
        pass

    # PDB fallback
    try:
        pdb = Gimp.get_pdb()
        proc = pdb.lookup_procedure("gimp-item-get-offset")
        if proc:
            cfg = proc.create_config()
            cfg.set_property("item", layer)
            res = proc.run(cfg)
            return int(res.index(0)), int(res.index(1))
    except Exception:
        pass

    return 0, 0


# ═══════════════════════════════════════════════════════════════════════════════
# 2. DISPATCH HANDLERS: Phase 1 — Session, File I/O & Canvas Geometry
# ═══════════════════════════════════════════════════════════════════════════════


class ToolDispatcher:
    def __init__(self):
        self.handlers = {}
        self._register_phase1_handlers()
        self._register_phase2_handlers()
        self._register_phase3_handlers()
        self._register_phase4_handlers()
        self._register_phase5_handlers()

    def register(self, name, handler):
        self.handlers[name] = handler

    def dispatch(self, cmd_type, params):
        if cmd_type not in self.handlers:
            return make_error_response("UnknownCommandError", f"Unknown tool or command '{cmd_type}'")
        try:
            return self.handlers[cmd_type](params)
        except Exception as e:
            traceback.print_exc()
            return make_error_response(type(e).__name__, str(e))

    def _register_phase1_handlers(self):
        # 1. Ping / Server Check
        self.register("ping", self._handle_ping)
        self.register("get_gimp_info", self._handle_get_gimp_info)

        # Phase 1: 10 Tools
        self.register("load_image", self._handle_load_image)
        self.register("export_image", self._handle_export_image)
        self.register("duplicate_image", self._handle_duplicate_image)
        self.register("close_image", self._handle_close_image)
        self.register("get_image_info", self._handle_get_image_info)
        self.register("resize_image", self._handle_resize_image)
        self.register("scale_image", self._handle_scale_image)
        self.register("crop_image", self._handle_crop_image)
        self.register("rotate_image", self._handle_rotate_image)
        self.register("flip_image", self._handle_flip_image)

    # ──────────────────────────────────────────────────────────────────────────
    # Core Diagnostics
    # ──────────────────────────────────────────────────────────────────────────
    def _handle_ping(self, params):
        return make_success_response({"pong": True, "message": "GIMP Agent Server is alive and responsive"})

    def _handle_get_gimp_info(self, params):
        return make_success_response({
            "version": Gimp.version(),
            "open_images": len(Gimp.get_images()),
            "platform": sys.platform
        })

    # ──────────────────────────────────────────────────────────────────────────
    # Phase 1 Tools Implementation
    # ──────────────────────────────────────────────────────────────────────────

    def _handle_load_image(self, params):
        """Tool 1: load_image(path)"""
        path = params.get("path")
        if not path:
            return make_error_response("ValueError", "Parameter 'path' is required")
        if not os.path.exists(path):
            return make_error_response("FileNotFoundError", f"Image file not found: {path}")

        gio_file = Gio.file_new_for_path(os.path.abspath(path))
        image = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, gio_file)
        if not image:
            return make_error_response("LoadError", f"Failed to load image from path: {path}")

        Gimp.Display.new(image)
        Gimp.displays_flush()
        return make_success_response({
            "loaded": True,
            "image_id": image.get_id(),
            "width": image.get_width(),
            "height": image.get_height()
        }, image)

    def _handle_export_image(self, params):
        """Tool 2: export_image(image_id, path, format)"""
        image_id = params.get("image_id")
        path = params.get("path")
        if not path:
            return make_error_response("ValueError", "Parameter 'path' is required")

        image = get_image_by_id(image_id)
        if not image:
            return make_error_response("ImageNotFoundError", f"Image id '{image_id}' not found")

        # Ensure parent directories exist
        out_dir = os.path.dirname(os.path.abspath(path))
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        # Duplicate & flatten for clean export without altering active canvas
        export_img = image.duplicate()
        drawable = export_img.flatten()
        
        gio_file = Gio.file_new_for_path(os.path.abspath(path))
        success = Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, export_img, gio_file)
        export_img.delete()

        if not success:
            return make_error_response("ExportError", f"Gimp.file_save failed for {path}", image)

        return make_success_response({
            "exported": True,
            "path": os.path.abspath(path),
            "file_size": os.path.getsize(os.path.abspath(path)) if os.path.exists(os.path.abspath(path)) else 0
        }, image)

    def _handle_duplicate_image(self, params):
        """Tool 3: duplicate_image(image_id)"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "Image not found")

        dup = image.duplicate()
        Gimp.Display.new(dup)
        Gimp.displays_flush()
        return make_success_response({
            "duplicated": True,
            "original_image_id": image.get_id(),
            "new_image_id": dup.get_id()
        }, dup)

    def _handle_close_image(self, params):
        """Tool 4: close_image(image_id)"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "Image not found")

        closed_id = image.get_id()
        image.delete()
        Gimp.displays_flush()
        return make_success_response({
            "closed": True,
            "closed_image_id": closed_id
        }, None)

    def _handle_get_image_info(self, params):
        """Tool 5: get_image_info(image_id)"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "No open image found")
        return make_success_response({"info": "Image information retrieved successfully"}, image)

    def _handle_resize_image(self, params):
        """Tool 6: resize_image(image_id, width, height) — resize canvas (crop/pad)"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "Image not found")

        width = int(params.get("width", 0))
        height = int(params.get("height", 0))
        off_x = int(params.get("offset_x", 0))
        off_y = int(params.get("offset_y", 0))

        if width <= 0 or height <= 0:
            return make_error_response("ValueError", "Width and height must be positive integers", image)

        image.undo_group_start()
        try:
            image.resize(width, height, off_x, off_y)
        finally:
            image.undo_group_end()

        Gimp.displays_flush()
        return make_success_response({
            "resized": True,
            "width": image.get_width(),
            "height": image.get_height()
        }, image)

    def _handle_scale_image(self, params):
        """Tool 7: scale_image(image_id, percent / width, height)"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "Image not found")

        percent = params.get("percent")
        if percent is not None:
            pct = float(percent) / 100.0
            new_w = max(1, int(image.get_width() * pct))
            new_h = max(1, int(image.get_height() * pct))
        else:
            new_w = int(params.get("width", image.get_width()))
            new_h = int(params.get("height", image.get_height()))

        image.undo_group_start()
        try:
            image.scale(new_w, new_h)
        finally:
            image.undo_group_end()

        Gimp.displays_flush()
        return make_success_response({
            "scaled": True,
            "width": image.get_width(),
            "height": image.get_height()
        }, image)

    def _handle_crop_image(self, params):
        """Tool 8: crop_image(image_id, x, y, width, height)"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "Image not found")

        x = int(params.get("x", 0))
        y = int(params.get("y", 0))
        width = int(params.get("width", 0))
        height = int(params.get("height", 0))

        if width <= 0 or height <= 0:
            return make_error_response("ValueError", "Width and height must be positive integers", image)

        image.undo_group_start()
        try:
            image.crop(width, height, x, y)
        finally:
            image.undo_group_end()

        Gimp.displays_flush()
        return make_success_response({
            "cropped": True,
            "x": x,
            "y": y,
            "width": image.get_width(),
            "height": image.get_height()
        }, image)

    def _handle_rotate_image(self, params):
        """Tool 9: rotate_image(image_id, degrees)"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "Image not found")

        degrees = float(params.get("degrees", 90))
        # Map to Gimp.RotationType
        # 90 -> Gimp.RotationType.ROTATION_90, 180 -> ROTATION_180, 270/-90 -> ROTATION_270
        deg_norm = int(degrees) % 360
        rot_type = Gimp.RotationType.ROTATION_90
        if deg_norm == 180:
            rot_type = Gimp.RotationType.ROTATION_180
        elif deg_norm in (270, -90):
            rot_type = Gimp.RotationType.ROTATION_270

        image.undo_group_start()
        try:
            image.rotate(rot_type)
        finally:
            image.undo_group_end()

        Gimp.displays_flush()
        return make_success_response({
            "rotated": True,
            "degrees": deg_norm,
            "width": image.get_width(),
            "height": image.get_height()
        }, image)

    def _handle_flip_image(self, params):
        """Tool 10: flip_image(image_id, axis) — axis: 'horizontal' / 'vertical' / 'h' / 'v'"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "Image not found")

        axis_str = str(params.get("axis", "horizontal")).lower()
        flip_type = Gimp.OrientationType.HORIZONTAL if ("h" in axis_str) else Gimp.OrientationType.VERTICAL

        image.undo_group_start()
        try:
            image.flip(flip_type)
        finally:
            image.undo_group_end()

        Gimp.displays_flush()
        return make_success_response({
            "flipped": True,
            "axis": "horizontal" if flip_type == Gimp.OrientationType.HORIZONTAL else "vertical"
        }, image)

    def _register_phase2_handlers(self):
        # Phase 2: Selections & Color Adjustments (10 Tools)
        self.register("select_rectangle", self._handle_select_rectangle)
        self.register("select_ellipse", self._handle_select_ellipse)
        self.register("select_by_color", self._handle_select_by_color)
        self.register("select_all", self._handle_select_all)
        self.register("select_none", self._handle_select_none)
        self.register("invert_selection", self._handle_invert_selection)
        self.register("adjust_brightness_contrast", self._handle_adjust_brightness_contrast)
        self.register("adjust_hue_saturation", self._handle_adjust_hue_saturation)
        self.register("adjust_levels", self._handle_adjust_levels)
        self.register("desaturate", self._handle_desaturate)

    # ──────────────────────────────────────────────────────────────────────────
    # Phase 2 Tools Implementation
    # ──────────────────────────────────────────────────────────────────────────

    def _handle_select_rectangle(self, params):
        """Tool 11: select_rectangle(image_id, x, y, width, height)"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "Image not found")

        x = int(params.get("x", 0))
        y = int(params.get("y", 0))
        width = int(params.get("width", 0))
        height = int(params.get("height", 0))

        if width <= 0 or height <= 0:
            return make_error_response("ValueError", "Width and height must be positive integers", image)

        image.undo_group_start()
        try:
            image.select_rectangle(Gimp.ChannelOps.REPLACE, x, y, width, height)
        finally:
            image.undo_group_end()

        Gimp.displays_flush()
        return make_success_response({
            "selected": True,
            "type": "rectangle",
            "x": x,
            "y": y,
            "width": width,
            "height": height
        }, image)

    def _handle_select_ellipse(self, params):
        """Tool 12: select_ellipse(image_id, x, y, width, height)"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "Image not found")

        x = int(params.get("x", 0))
        y = int(params.get("y", 0))
        width = int(params.get("width", 0))
        height = int(params.get("height", 0))

        if width <= 0 or height <= 0:
            return make_error_response("ValueError", "Width and height must be positive integers", image)

        image.undo_group_start()
        try:
            image.select_ellipse(Gimp.ChannelOps.REPLACE, x, y, width, height)
        finally:
            image.undo_group_end()

        Gimp.displays_flush()
        return make_success_response({
            "selected": True,
            "type": "ellipse",
            "x": x,
            "y": y,
            "width": width,
            "height": height
        }, image)

    def _handle_select_by_color(self, params):
        """Tool 13: select_by_color(image_id, x, y, threshold, color)"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "Image not found")

        drawable = get_layer_by_id(image, params.get("layer_id"))
        if not drawable:
            return make_error_response("LayerNotFoundError", "Target layer not found", image)

        threshold = int(params.get("threshold", 15))
        color_val = params.get("color")
        x_val = params.get("x")
        y_val = params.get("y")

        image.undo_group_start()
        try:
            pdb = Gimp.get_pdb()
            if color_val is not None:
                gegl_col = parse_color_to_gegl(color_val)
                proc = pdb.lookup_procedure("gimp-image-select-color")
                if proc:
                    cfg = proc.create_config()
                    cfg.set_property("image", image)
                    cfg.set_property("drawable", drawable)
                    cfg.set_property("color", gegl_col)
                    cfg.set_property("operation", Gimp.ChannelOps.REPLACE)
                    proc.run(cfg)
            elif x_val is not None and y_val is not None:
                proc = pdb.lookup_procedure("gimp-image-select-contiguous-color")
                if proc:
                    cfg = proc.create_config()
                    cfg.set_property("image", image)
                    cfg.set_property("drawable", drawable)
                    cfg.set_property("x", float(x_val))
                    cfg.set_property("y", float(y_val))
                    cfg.set_property("operation", Gimp.ChannelOps.REPLACE)
                    proc.run(cfg)
            else:
                # Default to current foreground color
                fg = Gimp.context_get_foreground()
                proc = pdb.lookup_procedure("gimp-image-select-color")
                if proc:
                    cfg = proc.create_config()
                    cfg.set_property("image", image)
                    cfg.set_property("drawable", drawable)
                    cfg.set_property("color", fg)
                    cfg.set_property("operation", Gimp.ChannelOps.REPLACE)
                    proc.run(cfg)
        finally:
            image.undo_group_end()

        Gimp.displays_flush()
        return make_success_response({
            "selected": True,
            "type": "color_selection",
            "threshold": threshold
        }, image)

    def _handle_select_all(self, params):
        """Tool 14: select_all(image_id)"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "Image not found")

        Gimp.Selection.all(image)
        Gimp.displays_flush()
        return make_success_response({"selected_all": True}, image)

    def _handle_select_none(self, params):
        """Tool 15: select_none(image_id)"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "Image not found")

        Gimp.Selection.none(image)
        Gimp.displays_flush()
        return make_success_response({"cleared_selection": True}, image)

    def _handle_invert_selection(self, params):
        """Tool 16: invert_selection(image_id)"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "Image not found")

        Gimp.Selection.invert(image)
        Gimp.displays_flush()
        return make_success_response({"inverted_selection": True}, image)

    def _handle_adjust_brightness_contrast(self, params):
        """Tool 17: adjust_brightness_contrast(image_id, layer_id, brightness, contrast)"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "Image not found")

        drawable = get_layer_by_id(image, params.get("layer_id"))
        if not drawable:
            return make_error_response("LayerNotFoundError", "Target layer not found", image)

        # Scale from -100..100 or -1.0..1.0 to -0.5..0.5 / -1.0..1.0
        b_raw = float(params.get("brightness", 0.0))
        c_raw = float(params.get("contrast", 0.0))
        b_val = b_raw / 100.0 if abs(b_raw) > 1.0 else b_raw
        c_val = c_raw / 100.0 if abs(c_raw) > 1.0 else c_raw

        image.undo_group_start()
        try:
            pdb = Gimp.get_pdb()
            proc = pdb.lookup_procedure("gimp-drawable-brightness-contrast")
            if proc:
                cfg = proc.create_config()
                cfg.set_property("drawable", drawable)
                cfg.set_property("brightness", b_val)
                cfg.set_property("contrast", c_val)
                proc.run(cfg)
            else:
                drawable.brightness_contrast(b_val, c_val)
        finally:
            image.undo_group_end()

        Gimp.displays_flush()
        return make_success_response({
            "adjusted": True,
            "layer_id": drawable.get_id(),
            "brightness": b_val,
            "contrast": c_val
        }, image)

    def _handle_adjust_hue_saturation(self, params):
        """Tool 18: adjust_hue_saturation(image_id, layer_id, hue, lightness, saturation)"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "Image not found")

        drawable = get_layer_by_id(image, params.get("layer_id"))
        if not drawable:
            return make_error_response("LayerNotFoundError", "Target layer not found", image)

        hue = float(params.get("hue", 0.0))
        lightness = float(params.get("lightness", 0.0))
        saturation = float(params.get("saturation", 0.0))

        image.undo_group_start()
        try:
            pdb = Gimp.get_pdb()
            proc = pdb.lookup_procedure("gimp-drawable-hue-saturation")
            if proc:
                cfg = proc.create_config()
                cfg.set_property("drawable", drawable)
                cfg.set_property("hue-range", Gimp.HueRange.ALL)
                cfg.set_property("hue-offset", hue)
                cfg.set_property("lightness", lightness)
                cfg.set_property("saturation", saturation)
                cfg.set_property("overlap", 0.0)
                proc.run(cfg)
            else:
                drawable.hue_saturation(Gimp.HueRange.ALL, hue, lightness, saturation, 0.0)
        finally:
            image.undo_group_end()

        Gimp.displays_flush()
        return make_success_response({
            "adjusted": True,
            "layer_id": drawable.get_id(),
            "hue": hue,
            "lightness": lightness,
            "saturation": saturation
        }, image)

    def _handle_adjust_levels(self, params):
        """Tool 19: adjust_levels(image_id, layer_id, channel, low_input, high_input, gamma)"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "Image not found")

        drawable = get_layer_by_id(image, params.get("layer_id"))
        if not drawable:
            return make_error_response("LayerNotFoundError", "Target layer not found", image)

        channel_map = {
            "value": Gimp.HistogramChannel.VALUE,
            "red": Gimp.HistogramChannel.RED,
            "green": Gimp.HistogramChannel.GREEN,
            "blue": Gimp.HistogramChannel.BLUE,
            "alpha": Gimp.HistogramChannel.ALPHA
        }
        chan_str = str(params.get("channel", "value")).lower()
        channel = channel_map.get(chan_str, Gimp.HistogramChannel.VALUE)

        low_in = float(params.get("low_input", 0.0))
        high_in = float(params.get("high_input", 1.0 if low_in <= 1.0 else 255.0))
        low_norm = low_in / 255.0 if low_in > 1.0 else low_in
        high_norm = high_in / 255.0 if high_in > 1.0 else high_in
        gamma = float(params.get("gamma", 1.0))

        image.undo_group_start()
        try:
            pdb = Gimp.get_pdb()
            proc = pdb.lookup_procedure("gimp-drawable-levels")
            if proc:
                cfg = proc.create_config()
                cfg.set_property("drawable", drawable)
                cfg.set_property("channel", channel)
                cfg.set_property("low-input", low_norm)
                cfg.set_property("high-input", high_norm)
                cfg.set_property("gamma", gamma)
                cfg.set_property("low-output", 0.0)
                cfg.set_property("high-output", 1.0)
                proc.run(cfg)
            else:
                drawable.levels(channel, low_norm, high_norm, False, gamma, 0.0, 1.0, False)
        finally:
            image.undo_group_end()

        Gimp.displays_flush()
        return make_success_response({
            "adjusted": True,
            "layer_id": drawable.get_id(),
            "channel": chan_str,
            "low_input": low_norm,
            "high_input": high_norm,
            "gamma": gamma
        }, image)

    def _handle_desaturate(self, params):
        """Tool 20: desaturate(image_id, layer_id, mode)"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "Image not found")

        drawable = get_layer_by_id(image, params.get("layer_id"))
        if not drawable:
            return make_error_response("LayerNotFoundError", "Target layer not found", image)

        mode_map = {
            "luminosity": Gimp.DesaturateMode.LUMINANCE,
            "luminance": Gimp.DesaturateMode.LUMINANCE,
            "average": Gimp.DesaturateMode.AVERAGE,
            "lightness": Gimp.DesaturateMode.LIGHTNESS,
            "value": Gimp.DesaturateMode.VALUE if hasattr(Gimp.DesaturateMode, "VALUE") else Gimp.DesaturateMode.LUMINANCE
        }
        mode_str = str(params.get("mode", "luminance")).lower()
        mode = mode_map.get(mode_str, Gimp.DesaturateMode.LUMINANCE)

        image.undo_group_start()
        try:
            pdb = Gimp.get_pdb()
            proc = pdb.lookup_procedure("gimp-drawable-desaturate")
            if proc:
                cfg = proc.create_config()
                cfg.set_property("drawable", drawable)
                cfg.set_property("desaturate-mode", mode)
                proc.run(cfg)
            else:
                drawable.desaturate(mode)
        finally:
            image.undo_group_end()

        Gimp.displays_flush()
        return make_success_response({
            "desaturated": True,
            "layer_id": drawable.get_id(),
            "mode": mode_str
        }, image)

    def _apply_gegl_filter(self, image, drawable, op_name, props):
        """
        Apply a GEGL operation to a drawable via the non-destructive filter API.
        Raises on failure so callers get a structured error rather than a silent no-op.
        """
        pdb = Gimp.get_pdb()
        filter_proc = pdb.lookup_procedure("gimp-drawable-filter-new")
        if not filter_proc:
            raise RuntimeError(
                f"GEGL filter API 'gimp-drawable-filter-new' is not available in this GIMP build. "
                f"Cannot apply '{op_name}'."
            )

        cfg = filter_proc.create_config()
        cfg.set_property("drawable", drawable)
        cfg.set_property("operation-name", op_name)
        cfg.set_property("name", op_name)
        result = filter_proc.run(cfg)

        # result.index(0) returns the DrawableFilter object; raise if absent.
        filtr = result.index(0)
        if filtr is None:
            raise RuntimeError(f"GEGL op '{op_name}' returned no filter object.")

        # Apply per-property settings — raise with context on first failure.
        for k, v in props.items():
            try:
                filtr.set_property(k, v)
            except Exception as prop_err:
                raise RuntimeError(
                    f"Failed to set GEGL property '{k}'={v!r} on op '{op_name}': {prop_err}"
                ) from prop_err

        apply_proc = pdb.lookup_procedure("gimp-drawable-merge-filter")
        if not apply_proc:
            raise RuntimeError(
                f"GEGL merge API 'gimp-drawable-merge-filter' is not available. "
                f"Filter '{op_name}' was created but could not be applied."
            )
        acfg = apply_proc.create_config()
        acfg.set_property("drawable", drawable)
        acfg.set_property("filter", filtr)
        apply_proc.run(acfg)

    def _register_phase3_handlers(self):
        # Phase 3: More Color, Filters & Effects (10 Tools)
        self.register("adjust_curves", self._handle_adjust_curves)
        self.register("adjust_color_balance", self._handle_adjust_color_balance)
        self.register("invert_colors", self._handle_invert_colors)
        self.register("apply_gaussian_blur", self._handle_apply_gaussian_blur)
        self.register("apply_motion_blur", self._handle_apply_motion_blur)
        self.register("apply_sharpen", self._handle_apply_sharpen)
        self.register("apply_pixelize", self._handle_apply_pixelize)
        self.register("apply_emboss", self._handle_apply_emboss)
        self.register("apply_noise", self._handle_apply_noise)
        self.register("apply_edge_detect", self._handle_apply_edge_detect)

    # ──────────────────────────────────────────────────────────────────────────
    # Phase 3 Tools Implementation
    # ──────────────────────────────────────────────────────────────────────────

    def _handle_adjust_curves(self, params):
        """Tool 21: adjust_curves(image_id, layer_id, preset)"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "Image not found")

        drawable = get_layer_by_id(image, params.get("layer_id"))
        if not drawable:
            return make_error_response("LayerNotFoundError", "Target layer not found", image)

        presets = {
            "s_curve":          [0.0, 0.0, 0.25, 0.18, 0.75, 0.82, 1.0, 1.0],
            "lighten":          [0.0, 0.0, 0.5, 0.7, 1.0, 1.0],
            "darken":           [0.0, 0.0, 0.5, 0.3, 1.0, 1.0],
            "increase_contrast":[0.0, 0.0, 0.2, 0.1, 0.8, 0.9, 1.0, 1.0],
            "lift_shadows":     [0.0, 0.18, 0.4, 0.55, 1.0, 1.0],
            "fade_highlights":  [0.0, 0.0, 0.6, 0.5, 1.0, 0.85],
            "linear":           [0.0, 0.0, 1.0, 1.0]
        }
        preset_name = str(params.get("preset", "s_curve")).lower()
        pts = presets.get(preset_name, presets["s_curve"])

        image.undo_group_start()
        try:
            try:
                drawable.curves_spline(Gimp.HistogramChannel.VALUE, pts)
            except Exception:
                import array
                typed_arr = array.array('d', pts)
                pdb = Gimp.get_pdb()
                proc = pdb.lookup_procedure("gimp-drawable-curves-spline")
                if proc:
                    cfg = proc.create_config()
                    cfg.set_property("drawable", drawable)
                    cfg.set_property("channel", Gimp.HistogramChannel.VALUE)
                    cfg.set_property("points", typed_arr)
                    proc.run(cfg)
        finally:
            image.undo_group_end()

        Gimp.displays_flush()
        return make_success_response({
            "adjusted_curves": True,
            "layer_id": drawable.get_id(),
            "preset": preset_name
        }, image)

    def _handle_adjust_color_balance(self, params):
        """Tool 22: adjust_color_balance(image_id, layer_id, cyan_red, magenta_green, yellow_blue, range)"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "Image not found")

        drawable = get_layer_by_id(image, params.get("layer_id"))
        if not drawable:
            return make_error_response("LayerNotFoundError", "Target layer not found", image)

        # Map tonal range string to GIMP 3.x TransferMode enum (not a raw int).
        range_str = str(params.get("range", "midtones")).lower()
        transfer_mode_map = {
            "shadows":    Gimp.TransferMode.SHADOWS,
            "midtones":   Gimp.TransferMode.MIDTONES,
            "highlights": Gimp.TransferMode.HIGHLIGHTS,
        }
        transfer_mode = transfer_mode_map.get(range_str, Gimp.TransferMode.MIDTONES)

        cr = float(params.get("cyan_red", 0.0))
        mg = float(params.get("magenta_green", 0.0))
        yb = float(params.get("yellow_blue", 0.0))
        # Normalize to -1.0..1.0 (accept both 0-100 and 0-1 inputs)
        cr_norm = cr / 100.0 if abs(cr) > 1.0 else cr
        mg_norm = mg / 100.0 if abs(mg) > 1.0 else mg
        yb_norm = yb / 100.0 if abs(yb) > 1.0 else yb

        image.undo_group_start()
        try:
            pdb = Gimp.get_pdb()
            proc = pdb.lookup_procedure("gimp-drawable-color-balance")
            if proc:
                cfg = proc.create_config()
                cfg.set_property("drawable", drawable)
                cfg.set_property("transfer-mode", transfer_mode)  # Gimp.TransferMode enum
                cfg.set_property("cyan-red", cr_norm)
                cfg.set_property("magenta-green", mg_norm)
                cfg.set_property("yellow-blue", yb_norm)
                cfg.set_property("preserve-lum", True)
                proc.run(cfg)
        finally:
            image.undo_group_end()

        Gimp.displays_flush()
        return make_success_response({
            "adjusted_color_balance": True,
            "layer_id": drawable.get_id(),
            "cyan_red": cr_norm,
            "magenta_green": mg_norm,
            "yellow_blue": yb_norm
        }, image)

    def _handle_invert_colors(self, params):
        """Tool 23: invert_colors(image_id, layer_id)"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "Image not found")

        drawable = get_layer_by_id(image, params.get("layer_id"))
        if not drawable:
            return make_error_response("LayerNotFoundError", "Target layer not found", image)

        image.undo_group_start()
        try:
            pdb = Gimp.get_pdb()
            proc = pdb.lookup_procedure("gimp-drawable-invert")
            if proc:
                cfg = proc.create_config()
                cfg.set_property("drawable", drawable)
                cfg.set_property("linear", False)
                proc.run(cfg)
            else:
                drawable.invert(False)
        finally:
            image.undo_group_end()

        Gimp.displays_flush()
        return make_success_response({
            "inverted": True,
            "layer_id": drawable.get_id()
        }, image)

    def _handle_apply_gaussian_blur(self, params):
        """Tool 24: apply_gaussian_blur(image_id, layer_id, radius)"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "Image not found")

        drawable = get_layer_by_id(image, params.get("layer_id"))
        if not drawable:
            return make_error_response("LayerNotFoundError", "Target layer not found", image)

        radius = float(params.get("radius", 5.0))

        image.undo_group_start()
        try:
            pdb = Gimp.get_pdb()
            proc = pdb.lookup_procedure("plug-in-gauss")
            if proc:
                cfg = proc.create_config()
                cfg.set_property("image", image)
                cfg.set_property("drawable", drawable)
                cfg.set_property("horizontal", int(radius * 2 + 1))
                cfg.set_property("vertical", int(radius * 2 + 1))
                cfg.set_property("method", 0)
                proc.run(cfg)
            else:
                self._apply_gegl_filter(image, drawable, "gegl:gaussian-blur", {
                    "std-dev-x": radius,
                    "std-dev-y": radius
                })
        finally:
            image.undo_group_end()

        Gimp.displays_flush()
        return make_success_response({
            "applied_blur": True,
            "layer_id": drawable.get_id(),
            "radius": radius
        }, image)

    def _handle_apply_motion_blur(self, params):
        """Tool 25: apply_motion_blur(image_id, layer_id, angle, length)"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "Image not found")

        drawable = get_layer_by_id(image, params.get("layer_id"))
        if not drawable:
            return make_error_response("LayerNotFoundError", "Target layer not found", image)

        angle = float(params.get("angle", 45.0))
        length = float(params.get("length", 10.0))

        image.undo_group_start()
        try:
            self._apply_gegl_filter(image, drawable, "gegl:motion-blur-linear", {
                "angle": angle,
                "length": length
            })
        finally:
            image.undo_group_end()

        Gimp.displays_flush()
        return make_success_response({
            "applied_motion_blur": True,
            "layer_id": drawable.get_id(),
            "angle": angle,
            "length": length
        }, image)

    def _handle_apply_sharpen(self, params):
        """Tool 26: apply_sharpen(image_id, layer_id, amount, radius, threshold)"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "Image not found")

        drawable = get_layer_by_id(image, params.get("layer_id"))
        if not drawable:
            return make_error_response("LayerNotFoundError", "Target layer not found", image)

        amount = float(params.get("amount", 50.0))
        radius = float(params.get("radius", 3.0))
        threshold = int(params.get("threshold", 0))

        image.undo_group_start()
        try:
            pdb = Gimp.get_pdb()
            proc = pdb.lookup_procedure("plug-in-unsharp-mask")
            if proc:
                cfg = proc.create_config()
                cfg.set_property("image", image)
                cfg.set_property("drawable", drawable)
                cfg.set_property("radius", radius)
                cfg.set_property("amount", amount / 100.0 if amount > 1.0 else amount)
                cfg.set_property("threshold", threshold)
                proc.run(cfg)
            else:
                self._apply_gegl_filter(image, drawable, "gegl:unsharp-mask", {
                    "std-dev": radius,
                    "scale": amount / 100.0 if amount > 1.0 else amount,
                    "threshold": threshold / 255.0
                })
        finally:
            image.undo_group_end()

        Gimp.displays_flush()
        return make_success_response({
            "applied_sharpen": True,
            "layer_id": drawable.get_id(),
            "amount": amount
        }, image)

    def _handle_apply_pixelize(self, params):
        """Tool 27: apply_pixelize(image_id, layer_id, block_size)"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "Image not found")

        drawable = get_layer_by_id(image, params.get("layer_id"))
        if not drawable:
            return make_error_response("LayerNotFoundError", "Target layer not found", image)

        block_size = int(params.get("block_size", 10))

        image.undo_group_start()
        try:
            self._apply_gegl_filter(image, drawable, "gegl:pixelize", {
                "size-x": block_size,
                "size-y": block_size
            })
        finally:
            image.undo_group_end()

        Gimp.displays_flush()
        return make_success_response({
            "applied_pixelize": True,
            "layer_id": drawable.get_id(),
            "block_size": block_size
        }, image)

    def _handle_apply_emboss(self, params):
        """Tool 28: apply_emboss(image_id, layer_id, azimuth, elevation)"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "Image not found")

        drawable = get_layer_by_id(image, params.get("layer_id"))
        if not drawable:
            return make_error_response("LayerNotFoundError", "Target layer not found", image)

        azimuth = float(params.get("azimuth", 30.0))
        elevation = float(params.get("elevation", 45.0))

        image.undo_group_start()
        try:
            self._apply_gegl_filter(image, drawable, "gegl:emboss", {
                "azimuth": azimuth,
                "elevation": elevation
            })
        finally:
            image.undo_group_end()

        Gimp.displays_flush()
        return make_success_response({
            "applied_emboss": True,
            "layer_id": drawable.get_id(),
            "azimuth": azimuth,
            "elevation": elevation
        }, image)

    def _handle_apply_noise(self, params):
        """Tool 29: apply_noise(image_id, layer_id, amount)"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "Image not found")

        drawable = get_layer_by_id(image, params.get("layer_id"))
        if not drawable:
            return make_error_response("LayerNotFoundError", "Target layer not found", image)

        amount = float(params.get("amount", 20.0))
        norm_amt = amount / 100.0 if amount > 1.0 else amount

        image.undo_group_start()
        try:
            self._apply_gegl_filter(image, drawable, "gegl:noise-rgb", {
                "red": norm_amt,
                "green": norm_amt,
                "blue": norm_amt
            })
        finally:
            image.undo_group_end()

        Gimp.displays_flush()
        return make_success_response({
            "applied_noise": True,
            "layer_id": drawable.get_id(),
            "amount": amount
        }, image)

    def _handle_apply_edge_detect(self, params):
        """Tool 30: apply_edge_detect(image_id, layer_id, algorithm)"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "Image not found")

        drawable = get_layer_by_id(image, params.get("layer_id"))
        if not drawable:
            return make_error_response("LayerNotFoundError", "Target layer not found", image)

        algo = str(params.get("algorithm", "sobel")).lower()

        image.undo_group_start()
        try:
            self._apply_gegl_filter(image, drawable, "gegl:edge-sobel", {})
        finally:
            image.undo_group_end()

        Gimp.displays_flush()
        return make_success_response({
            "applied_edge_detect": True,
            "layer_id": drawable.get_id(),
            "algorithm": algo
        }, image)

    def _register_phase4_handlers(self):
        # Phase 4: Layers (8 Tools)
        self.register("add_layer", self._handle_add_layer)
        self.register("delete_layer", self._handle_delete_layer)
        self.register("duplicate_layer", self._handle_duplicate_layer)
        self.register("merge_down", self._handle_merge_down)
        self.register("flatten_image", self._handle_flatten_image)
        self.register("set_layer_opacity", self._handle_set_layer_opacity)
        self.register("set_layer_blend_mode", self._handle_set_layer_blend_mode)
        self.register("rename_layer", self._handle_rename_layer)

    # ──────────────────────────────────────────────────────────────────────────
    # Phase 4 Tools Implementation
    # ──────────────────────────────────────────────────────────────────────────

    def _handle_add_layer(self, params):
        """Tool 31: add_layer(image_id, name, width, height, fill_type)"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "Image not found")

        name = str(params.get("name", "New Layer"))
        width = int(params.get("width", image.get_width()))
        height = int(params.get("height", image.get_height()))

        image.undo_group_start()
        try:
            new_layer = Gimp.Layer.new(
                image,
                name,
                width,
                height,
                Gimp.ImageType.RGBA_IMAGE,
                100.0,
                Gimp.LayerMode.NORMAL
            )
            image.insert_layer(new_layer, None, 0)

            fill_str = str(params.get("fill_type", "transparent")).lower()
            if fill_str in ("white", "background"):
                new_layer.edit_fill(Gimp.FillType.BACKGROUND)
            elif fill_str in ("black", "foreground"):
                new_layer.edit_fill(Gimp.FillType.FOREGROUND)
            elif fill_str == "transparent":
                new_layer.edit_fill(Gimp.FillType.TRANSPARENT)
        finally:
            image.undo_group_end()

        Gimp.displays_flush()
        return make_success_response({
            "added_layer": True,
            "layer_id": new_layer.get_id(),
            "name": name,
            "width": width,
            "height": height
        }, image)

    def _handle_delete_layer(self, params):
        """Tool 32: delete_layer(image_id, layer_id)"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "Image not found")

        layer = get_layer_by_id(image, params.get("layer_id"))
        if not layer:
            return make_error_response("LayerNotFoundError", "Layer to delete not found", image)

        layer_id = layer.get_id()
        image.undo_group_start()
        try:
            image.remove_layer(layer)
        finally:
            image.undo_group_end()

        Gimp.displays_flush()
        return make_success_response({
            "deleted_layer": True,
            "layer_id": layer_id
        }, image)

    def _handle_duplicate_layer(self, params):
        """Tool 33: duplicate_layer(image_id, layer_id)"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "Image not found")

        layer = get_layer_by_id(image, params.get("layer_id"))
        if not layer:
            return make_error_response("LayerNotFoundError", "Source layer not found", image)

        image.undo_group_start()
        try:
            dup_layer = layer.copy()
            image.insert_layer(dup_layer, None, 0)
        finally:
            image.undo_group_end()

        Gimp.displays_flush()
        return make_success_response({
            "duplicated_layer": True,
            "original_layer_id": layer.get_id(),
            "new_layer_id": dup_layer.get_id(),
            "name": dup_layer.get_name()
        }, image)

    def _handle_merge_down(self, params):
        """Tool 34: merge_down(image_id, layer_id)"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "Image not found")

        layer = get_layer_by_id(image, params.get("layer_id"))
        if not layer:
            return make_error_response("LayerNotFoundError", "Layer not found", image)

        image.undo_group_start()
        try:
            merged_layer = image.merge_down(layer, Gimp.MergeType.EXPAND_AS_NECESSARY)
        finally:
            image.undo_group_end()

        Gimp.displays_flush()
        return make_success_response({
            "merged_down": True,
            "merged_layer_id": merged_layer.get_id() if merged_layer else None
        }, image)

    def _handle_flatten_image(self, params):
        """Tool 35: flatten_image(image_id)"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "Image not found")

        image.undo_group_start()
        try:
            flat_layer = image.flatten()
        finally:
            image.undo_group_end()

        Gimp.displays_flush()
        return make_success_response({
            "flattened": True,
            "active_layer_id": flat_layer.get_id() if flat_layer else None
        }, image)

    def _handle_set_layer_opacity(self, params):
        """Tool 36: set_layer_opacity(image_id, layer_id, opacity) — opacity 0..100"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "Image not found")

        layer = get_layer_by_id(image, params.get("layer_id"))
        if not layer:
            return make_error_response("LayerNotFoundError", "Layer not found", image)

        op_val = float(params.get("opacity", 100.0))
        # Ensure 0..100
        op_clamped = max(0.0, min(100.0, op_val if op_val > 1.0 else op_val * 100.0))

        image.undo_group_start()
        try:
            layer.set_opacity(op_clamped)
        finally:
            image.undo_group_end()

        Gimp.displays_flush()
        return make_success_response({
            "opacity_set": True,
            "layer_id": layer.get_id(),
            "opacity": op_clamped
        }, image)

    def _handle_set_layer_blend_mode(self, params):
        """Tool 37: set_layer_blend_mode(image_id, layer_id, mode)"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "Image not found")

        layer = get_layer_by_id(image, params.get("layer_id"))
        if not layer:
            return make_error_response("LayerNotFoundError", "Layer not found", image)

        mode_map = {
            "normal": Gimp.LayerMode.NORMAL,
            "multiply": Gimp.LayerMode.MULTIPLY,
            "screen": Gimp.LayerMode.SCREEN,
            "overlay": Gimp.LayerMode.OVERLAY,
            "difference": Gimp.LayerMode.DIFFERENCE,
            "darken": Gimp.LayerMode.DARKEN_ONLY,
            "lighten": Gimp.LayerMode.LIGHTEN_ONLY,
            "addition": Gimp.LayerMode.ADDITION,
            "subtraction": Gimp.LayerMode.SUBTRACT
        }
        mode_str = str(params.get("mode", "normal")).lower()
        blend_mode = mode_map.get(mode_str, Gimp.LayerMode.NORMAL)

        image.undo_group_start()
        try:
            layer.set_mode(blend_mode)
        finally:
            image.undo_group_end()

        Gimp.displays_flush()
        return make_success_response({
            "blend_mode_set": True,
            "layer_id": layer.get_id(),
            "mode": mode_str
        }, image)

    def _handle_rename_layer(self, params):
        """Tool 38: rename_layer(image_id, layer_id, new_name)"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "Image not found")

        layer = get_layer_by_id(image, params.get("layer_id"))
        if not layer:
            return make_error_response("LayerNotFoundError", "Layer not found", image)

        new_name = str(params.get("new_name", "Layer"))
        image.undo_group_start()
        try:
            layer.set_name(new_name)
        finally:
            image.undo_group_end()

        Gimp.displays_flush()
        return make_success_response({
            "renamed": True,
            "layer_id": layer.get_id(),
            "new_name": new_name
        }, image)

    def _register_phase5_handlers(self):
        # Phase 5: Text, Drawing & Per-Layer Transforms (12 Tools)
        self.register("add_text_layer", self._handle_add_text_layer)
        self.register("draw_rectangle", self._handle_draw_rectangle)
        self.register("draw_ellipse", self._handle_draw_ellipse)
        self.register("draw_line", self._handle_draw_line)
        self.register("fill_selection", self._handle_fill_selection)
        self.register("move_layer", self._handle_move_layer)
        self.register("scale_layer", self._handle_scale_layer)
        self.register("rotate_layer", self._handle_rotate_layer)
        self.register("reorder_layer", self._handle_reorder_layer)
        self.register("feather_selection", self._handle_feather_selection)
        self.register("set_foreground_color", self._handle_set_foreground_color)
        self.register("get_layer_info", self._handle_get_layer_info)

    # ──────────────────────────────────────────────────────────────────────────
    # Phase 5 Tools Implementation
    # ──────────────────────────────────────────────────────────────────────────

    def _handle_add_text_layer(self, params):
        """Tool 39: add_text_layer(image_id, text, x, y, font, size, color)"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "Image not found")

        text = str(params.get("text", "Text"))
        x = int(params.get("x", 10))
        y = int(params.get("y", 10))
        font_name = str(params.get("font", "Sans-serif"))
        size = float(params.get("size", 24.0))
        color_val = params.get("color", "black")

        image.undo_group_start()
        try:
            pdb = Gimp.get_pdb()
            proc = pdb.lookup_procedure("gimp-text-fontname")
            text_layer = None
            if proc:
                cfg = proc.create_config()
                cfg.set_property("image", image)
                cfg.set_property("drawable", None)
                cfg.set_property("x", float(x))
                cfg.set_property("y", float(y))
                cfg.set_property("text", text)
                cfg.set_property("border", 0)
                cfg.set_property("antialias", True)
                cfg.set_property("size", size)
                cfg.set_property("size-type", Gimp.Unit.PIXEL)
                cfg.set_property("fontname", font_name)
                res = proc.run(cfg)
                try:
                    text_layer = res.index(0)
                except Exception:
                    pass

            if text_layer and color_val:
                try:
                    text_layer.set_color(parse_color_to_gegl(color_val))
                except Exception:
                    pass
        finally:
            image.undo_group_end()

        Gimp.displays_flush()
        return make_success_response({
            "added_text_layer": True,
            "layer_id": text_layer.get_id() if text_layer else None,
            "text": text,
            "x": x,
            "y": y
        }, image)

    def _handle_draw_rectangle(self, params):
        """Tool 40: draw_rectangle(image_id, layer_id, x, y, width, height, color, filled)"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "Image not found")

        drawable = get_layer_by_id(image, params.get("layer_id"))
        if not drawable:
            return make_error_response("LayerNotFoundError", "Target layer not found", image)

        x = int(params.get("x", 0))
        y = int(params.get("y", 0))
        width = int(params.get("width", 50))
        height = int(params.get("height", 50))
        color_val = params.get("color", "black")
        filled = bool(params.get("filled", True))

        image.undo_group_start()
        try:
            image.select_rectangle(Gimp.ChannelOps.REPLACE, x, y, width, height)
            Gimp.context_set_foreground(parse_color_to_gegl(color_val))
            if filled:
                drawable.edit_fill(Gimp.FillType.FOREGROUND)
            else:
                try:
                    drawable.edit_stroke_selection()
                except Exception:
                    drawable.edit_fill(Gimp.FillType.FOREGROUND)
            Gimp.Selection.none(image)
        finally:
            image.undo_group_end()

        Gimp.displays_flush()
        return make_success_response({
            "drawn_rectangle": True,
            "layer_id": drawable.get_id(),
            "x": x,
            "y": y,
            "width": width,
            "height": height
        }, image)

    def _handle_draw_ellipse(self, params):
        """Tool 41: draw_ellipse(image_id, layer_id, x, y, width, height, color, filled)"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "Image not found")

        drawable = get_layer_by_id(image, params.get("layer_id"))
        if not drawable:
            return make_error_response("LayerNotFoundError", "Target layer not found", image)

        x = int(params.get("x", 0))
        y = int(params.get("y", 0))
        width = int(params.get("width", 50))
        height = int(params.get("height", 50))
        color_val = params.get("color", "black")
        filled = bool(params.get("filled", True))

        image.undo_group_start()
        try:
            image.select_ellipse(Gimp.ChannelOps.REPLACE, x, y, width, height)
            Gimp.context_set_foreground(parse_color_to_gegl(color_val))
            if filled:
                drawable.edit_fill(Gimp.FillType.FOREGROUND)
            else:
                try:
                    drawable.edit_stroke_selection()
                except Exception:
                    drawable.edit_fill(Gimp.FillType.FOREGROUND)
            Gimp.Selection.none(image)
        finally:
            image.undo_group_end()

        Gimp.displays_flush()
        return make_success_response({
            "drawn_ellipse": True,
            "layer_id": drawable.get_id(),
            "x": x,
            "y": y,
            "width": width,
            "height": height
        }, image)

    def _handle_draw_line(self, params):
        """Tool 42: draw_line(image_id, layer_id, x1, y1, x2, y2, color, thickness)"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "Image not found")

        drawable = get_layer_by_id(image, params.get("layer_id"))
        if not drawable:
            return make_error_response("LayerNotFoundError", "Target layer not found", image)

        x1 = float(params.get("x1", 0))
        y1 = float(params.get("y1", 0))
        x2 = float(params.get("x2", 100))
        y2 = float(params.get("y2", 100))
        color_val = params.get("color", "black")
        thickness = float(params.get("thickness", 2.0))

        image.undo_group_start()
        try:
            Gimp.context_set_foreground(parse_color_to_gegl(color_val))
            Gimp.context_set_brush_size(thickness)
            try:
                Gimp.pencil(drawable, [x1, y1, x2, y2])
            except Exception:
                pdb = Gimp.get_pdb()
                proc = pdb.lookup_procedure("gimp-pencil")
                if proc:
                    import array
                    cfg = proc.create_config()
                    cfg.set_property("drawable", drawable)
                    cfg.set_property("stroke-points", array.array('d', [x1, y1, x2, y2]))
                    proc.run(cfg)
        finally:
            image.undo_group_end()

        Gimp.displays_flush()
        return make_success_response({
            "drawn_line": True,
            "layer_id": drawable.get_id(),
            "start": [x1, y1],
            "end": [x2, y2]
        }, image)

    def _handle_fill_selection(self, params):
        """Tool 43: fill_selection(image_id, layer_id, color)"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "Image not found")

        drawable = get_layer_by_id(image, params.get("layer_id"))
        if not drawable:
            return make_error_response("LayerNotFoundError", "Target layer not found", image)

        color_val = params.get("color", "black")
        image.undo_group_start()
        try:
            Gimp.context_set_foreground(parse_color_to_gegl(color_val))
            drawable.edit_fill(Gimp.FillType.FOREGROUND)
        finally:
            image.undo_group_end()

        Gimp.displays_flush()
        return make_success_response({
            "filled_selection": True,
            "layer_id": drawable.get_id()
        }, image)

    def _handle_move_layer(self, params):
        """Tool 44: move_layer(image_id, layer_id, x_offset, y_offset)"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "Image not found")

        layer = get_layer_by_id(image, params.get("layer_id"))
        if not layer:
            return make_error_response("LayerNotFoundError", "Layer not found", image)

        dx = int(params.get("x_offset", 0))
        dy = int(params.get("y_offset", 0))

        image.undo_group_start()
        try:
            # get_offsets() returns (success_bool, x, y) in GIMP 3.x GI.
            # Use safe tuple-unpack with PDB fallback to avoid index-into-wrong-type bugs.
            cur_x, cur_y = _get_layer_offsets(layer)
            layer.set_offsets(cur_x + dx, cur_y + dy)
        finally:
            image.undo_group_end()

        Gimp.displays_flush()
        return make_success_response({
            "moved_layer": True,
            "layer_id": layer.get_id(),
            "offset": [dx, dy]
        }, image)

    def _handle_scale_layer(self, params):
        """Tool 45: scale_layer(image_id, layer_id, width, height)"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "Image not found")

        layer = get_layer_by_id(image, params.get("layer_id"))
        if not layer:
            return make_error_response("LayerNotFoundError", "Layer not found", image)

        w = int(params.get("width", layer.get_width()))
        h = int(params.get("height", layer.get_height()))

        image.undo_group_start()
        try:
            layer.scale(w, h, False)
        finally:
            image.undo_group_end()

        Gimp.displays_flush()
        return make_success_response({
            "scaled_layer": True,
            "layer_id": layer.get_id(),
            "width": w,
            "height": h
        }, image)

    def _handle_rotate_layer(self, params):
        """Tool 46: rotate_layer(image_id, layer_id, degrees)"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "Image not found")

        layer = get_layer_by_id(image, params.get("layer_id"))
        if not layer:
            return make_error_response("LayerNotFoundError", "Layer not found", image)

        deg = float(params.get("degrees", 90.0))
        rad = math.radians(deg)

        image.undo_group_start()
        try:
            pdb = Gimp.get_pdb()
            proc = pdb.lookup_procedure("gimp-item-transform-rotate-default")
            if proc:
                cfg = proc.create_config()
                cfg.set_property("item", layer)
                cfg.set_property("angle", rad)
                cfg.set_property("auto-center", True)
                cfg.set_property("center-x", 0.0)
                cfg.set_property("center-y", 0.0)
                proc.run(cfg)
        finally:
            image.undo_group_end()

        Gimp.displays_flush()
        return make_success_response({
            "rotated_layer": True,
            "layer_id": layer.get_id(),
            "degrees": deg
        }, image)

    def _handle_reorder_layer(self, params):
        """Tool 47: reorder_layer(image_id, layer_id, new_position)"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "Image not found")

        layer = get_layer_by_id(image, params.get("layer_id"))
        if not layer:
            return make_error_response("LayerNotFoundError", "Layer not found", image)

        pos = int(params.get("new_position", 0))

        image.undo_group_start()
        try:
            image.reorder_item(layer, None, pos)
        finally:
            image.undo_group_end()

        Gimp.displays_flush()
        return make_success_response({
            "reordered_layer": True,
            "layer_id": layer.get_id(),
            "new_position": pos
        }, image)

    def _handle_feather_selection(self, params):
        """Tool 48: feather_selection(image_id, radius)"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "Image not found")

        radius = float(params.get("radius", 5.0))
        Gimp.Selection.feather(image, radius)
        Gimp.displays_flush()
        return make_success_response({
            "feathered_selection": True,
            "radius": radius
        }, image)

    def _handle_set_foreground_color(self, params):
        """Tool 49: set_foreground_color(color)"""
        color_val = params.get("color", "black")
        gegl_col = parse_color_to_gegl(color_val)
        Gimp.context_set_foreground(gegl_col)
        # Resolve optional image_id so image_state is grounded correctly.
        image = get_image_by_id(params.get("image_id"))
        return make_success_response({
            "foreground_color_set": True,
            "color": str(color_val)
        }, image)

    def _handle_get_layer_info(self, params):
        """Tool 50: get_layer_info(image_id, layer_id)"""
        image = get_image_by_id(params.get("image_id"))
        if not image:
            return make_error_response("ImageNotFoundError", "Image not found")

        layer = get_layer_by_id(image, params.get("layer_id"))
        if not layer:
            return make_error_response("LayerNotFoundError", "Layer not found", image)

        x_off, y_off = _get_layer_offsets(layer)

        return make_success_response({
            "layer_id": layer.get_id(),
            "name": layer.get_name(),
            "width": layer.get_width(),
            "height": layer.get_height(),
            "opacity": layer.get_opacity(),
            "visible": layer.get_visible(),
            "mode": str(layer.get_mode()),
            "offset_x": x_off,
            "offset_y": y_off
        }, image)






# ═══════════════════════════════════════════════════════════════════════════════
# 3. GIMP PLUGIN CLASS WITH THREAD-SAFE GLib MAIN-LOOP DISPATCH
# ═══════════════════════════════════════════════════════════════════════════════

class GimpAgentPlugin(Gimp.PlugIn):
    def __init__(self):
        super().__init__()
        self.host = DEFAULT_HOST
        self.port = DEFAULT_PORT
        self.running = False
        self.server_socket = None
        self.dispatcher = ToolDispatcher()
        self._glib_loop = None

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return [
            "plug-in-gimp-agent-server",
            "plug-in-gimp-agent-check",
            "plug-in-gimp-agent-stop"
        ]

    def do_create_procedure(self, name):
        if name == "plug-in-gimp-agent-check":
            proc = Gimp.Procedure.new(self, name, Gimp.PDBProcType.PLUGIN, self._run_check, None)
            proc.set_menu_label(_("Check AI Agent Server"))
            proc.set_documentation(_("Check if AI Agent Server is running"), _("Status of socket server"), name)
            proc.set_attribution("AI Image Edit", "AI Image Edit", "2026")
            proc.add_menu_path('<Image>/Tools/AI Agent')
            return proc

        if name == "plug-in-gimp-agent-stop":
            proc = Gimp.Procedure.new(self, name, Gimp.PDBProcType.PLUGIN, self._run_stop, None)
            proc.set_menu_label(_("Stop AI Agent Server"))
            proc.set_documentation(_("Stop AI Agent Server socket"), _("Stops socket on port 9877"), name)
            proc.set_attribution("AI Image Edit", "AI Image Edit", "2026")
            proc.add_menu_path('<Image>/Tools/AI Agent')
            return proc

        # Default: plug-in-gimp-agent-server
        proc = Gimp.Procedure.new(self, name, Gimp.PDBProcType.PLUGIN, self.run, None)
        proc.set_menu_label(_("Start AI Agent Server"))
        proc.set_documentation(_("Starts the AI Agent Socket Server (port 9877)"), _("Listens for agent tool commands"), name)
        proc.set_attribution("AI Image Edit", "AI Image Edit", "2026")
        proc.add_menu_path('<Image>/Tools/AI Agent')
        return proc

    def _run_check(self, procedure, config, run_data):
        status = "RUNNING" if self.running else "STOPPED"
        print(f"[GimpAgent] Server status: {status} on port {self.port}")
        return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())

    def _run_stop(self, procedure, config, run_data):
        self.stop_server()
        print(f"[GimpAgent] Server stopped")
        return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())

    def run(self, procedure, config, run_data):
        if self.running:
            print("[GimpAgent] Server is already running")
            return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())

        print(f"[GimpAgent] Starting server on {self.host}:{self.port}...")
        self.running = True

        # Launch socket accept loop in background thread
        server_thread = threading.Thread(target=self._server_socket_loop, daemon=True)
        server_thread.start()

        # Run GLib main loop on main thread to service UI & PDB calls safely
        self._glib_loop = GLib.MainLoop()
        self._glib_loop.run()

        return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())

    def stop_server(self):
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
            self.server_socket = None
        if self._glib_loop and self._glib_loop.is_running():
            self._glib_loop.quit()

    def _server_socket_loop(self):
        """Runs in background thread: accepts incoming connections."""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.settimeout(1.0)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            print(f"[GimpAgent] Socket server successfully listening on {self.host}:{self.port}")

            while self.running:
                try:
                    client_sock, client_addr = self.server_socket.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break

                # Handle client in dedicated thread
                client_t = threading.Thread(target=self._handle_client, args=(client_sock,), daemon=True)
                client_t.start()

        except Exception as e:
            print(f"[GimpAgent] Server socket error: {e}")
        finally:
            self.stop_server()

    def _handle_client(self, client_sock):
        """Receives JSON request, executes on MAIN THREAD via GLib.idle_add, and returns response."""
        try:
            client_sock.settimeout(DEFAULT_TIMEOUT_SECONDS)
            buffer = b""
            
            while True:
                chunk = client_sock.recv(4096)
                if not chunk:
                    break
                buffer += chunk
                # Check for valid complete JSON
                try:
                    req_str = buffer.decode("utf-8").strip()
                    if req_str:
                        json.loads(req_str)
                        break
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue

            if not buffer:
                client_sock.close()
                return

            req_json = json.loads(buffer.decode("utf-8").strip())
            cmd_type = req_json.get("type", "")
            params = req_json.get("params", {})

            # ── CRITICAL: Dispatch execution to GLib MAIN THREAD ───────────────
            response_data = self._dispatch_to_main_thread(cmd_type, params)

            resp_bytes = json.dumps(response_data).encode("utf-8")
            client_sock.sendall(resp_bytes)
        except Exception as e:
            err_resp = make_error_response(type(e).__name__, f"Socket handling exception: {str(e)}")
            try:
                client_sock.sendall(json.dumps(err_resp).encode("utf-8"))
            except Exception:
                pass
        finally:
            try:
                client_sock.close()
            except Exception:
                pass

    def _dispatch_to_main_thread(self, cmd_type, params):
        """
        Thread-safe GLib main loop dispatch.
        Guarantees that Gimp.* and Gegl.* calls run exclusively on the GIMP main event loop thread.
        """
        result_box = {}
        completed_event = threading.Event()

        def _glib_worker():
            try:
                result_box["response"] = self.dispatcher.dispatch(cmd_type, params)
            except Exception as ex:
                result_box["response"] = make_error_response(type(ex).__name__, str(ex))
            finally:
                completed_event.set()
            return False  # GLib.SOURCE_REMOVE

        GLib.idle_add(_glib_worker)
        
        # Wait for main thread execution
        finished = completed_event.wait(timeout=DEFAULT_TIMEOUT_SECONDS)
        if not finished:
            return make_error_response("TimeoutError", f"Execution timed out after {DEFAULT_TIMEOUT_SECONDS}s on GIMP main loop")
            
        return result_box.get("response", make_error_response("InternalError", "No response generated"))


# ═══════════════════════════════════════════════════════════════════════════════
# PLUGIN ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    Gimp.main(GimpAgentPlugin.__gtype__, sys.argv)
