#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ollama Tool Schemas for GIMP Agentic AI (Deliverable 6)
Defines OpenAI/Ollama compatible function schemas organized by category.
"""

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1: Session, File I/O & Canvas Geometry (10 Tools)
# ═══════════════════════════════════════════════════════════════════════════════

PHASE1_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "load_image",
            "description": "Open an image file from a local filesystem path into GIMP. Returns the new image_id and dimensions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The absolute or relative path to the image file on disk."
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "export_image",
            "description": "Flattens and exports the current image or specified image_id to a file path (e.g. .png, .jpg, .webp). Does not overwrite the canvas working state.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image to export. Defaults to the active open image if omitted."
                    },
                    "path": {
                        "type": "string",
                        "description": "Target destination file path where the exported image should be saved."
                    },
                    "format": {
                        "type": "string",
                        "description": "Export format ('png', 'jpg', 'webp', etc.). Defaults to file extension."
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "duplicate_image",
            "description": "Duplicates an open image to a new independent canvas for safe experimentation or branching.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image to duplicate. Defaults to the active image if omitted."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "close_image",
            "description": "Closes an open image and frees its allocated memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image to close. Defaults to the active image if omitted."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_image_info",
            "description": "Retrieves the current metadata and state of the image (dimensions, layers list, active layer, file path). Use this before making modification decisions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image. Defaults to the active open image if omitted."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "resize_image",
            "description": "Resizes the image canvas boundaries without scaling or stretching existing pixel content (crops or adds padding). For scaling content, use scale_image.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image. Defaults to active image."
                    },
                    "width": {
                        "type": "integer",
                        "description": "Target canvas width in pixels."
                    },
                    "height": {
                        "type": "integer",
                        "description": "Target canvas height in pixels."
                    },
                    "offset_x": {
                        "type": "integer",
                        "description": "Horizontal placement offset of existing layers inside new canvas (default 0)."
                    },
                    "offset_y": {
                        "type": "integer",
                        "description": "Vertical placement offset of existing layers inside new canvas (default 0)."
                    }
                },
                "required": ["width", "height"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "scale_image",
            "description": "Rescales the entire image content and canvas together by percentage or target dimensions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image. Defaults to active image."
                    },
                    "percent": {
                        "type": "number",
                        "description": "Scaling factor percentage (e.g. 50 for half size, 200 for double size)."
                    },
                    "width": {
                        "type": "integer",
                        "description": "Explicit new width in pixels (optional if percent is given)."
                    },
                    "height": {
                        "type": "integer",
                        "description": "Explicit new height in pixels (optional if percent is given)."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "crop_image",
            "description": "Crops the entire image canvas to a specified rectangular region (x, y, width, height).",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image. Defaults to active image."
                    },
                    "x": {
                        "type": "integer",
                        "description": "Left coordinate of crop box."
                    },
                    "y": {
                        "type": "integer",
                        "description": "Top coordinate of crop box."
                    },
                    "width": {
                        "type": "integer",
                        "description": "Width of crop box in pixels."
                    },
                    "height": {
                        "type": "integer",
                        "description": "Height of crop box in pixels."
                    }
                },
                "required": ["x", "y", "width", "height"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rotate_image",
            "description": "Rotates the entire image canvas by 90, 180, or 270 degrees.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image. Defaults to active image."
                    },
                    "degrees": {
                        "type": "number",
                        "description": "Rotation angle (90, 180, 270)."
                    }
                },
                "required": ["degrees"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "flip_image",
            "description": "Flips the entire image canvas horizontally or vertically.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image. Defaults to active image."
                    },
                    "axis": {
                        "type": "string",
                        "enum": ["horizontal", "vertical"],
                        "description": "Axis to flip across: 'horizontal' or 'vertical'."
                    }
                },
                "required": ["axis"]
            }
        }
    }
]


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2: Selections & Color Adjustments (10 Tools)
# ═══════════════════════════════════════════════════════════════════════════════

PHASE2_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "select_rectangle",
            "description": "Creates a rectangular selection on the image canvas (x, y, width, height).",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image. Defaults to active image."
                    },
                    "x": {
                        "type": "integer",
                        "description": "Left coordinate of selection."
                    },
                    "y": {
                        "type": "integer",
                        "description": "Top coordinate of selection."
                    },
                    "width": {
                        "type": "integer",
                        "description": "Width of selection."
                    },
                    "height": {
                        "type": "integer",
                        "description": "Height of selection."
                    }
                },
                "required": ["x", "y", "width", "height"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "select_ellipse",
            "description": "Creates an elliptical selection on the image canvas (x, y, width, height).",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image. Defaults to active image."
                    },
                    "x": {
                        "type": "integer",
                        "description": "Left coordinate of bounding box."
                    },
                    "y": {
                        "type": "integer",
                        "description": "Top coordinate of bounding box."
                    },
                    "width": {
                        "type": "integer",
                        "description": "Width of ellipse."
                    },
                    "height": {
                        "type": "integer",
                        "description": "Height of ellipse."
                    }
                },
                "required": ["x", "y", "width", "height"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "select_by_color",
            "description": "Selects contiguous or matching color areas across the layer. Groundwork for subject/background isolation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image. Defaults to active image."
                    },
                    "layer_id": {
                        "type": "integer",
                        "description": "Layer ID to sample from. Defaults to active layer if omitted."
                    },
                    "color": {
                        "type": "string",
                        "description": "Color name or hex string (e.g. 'white', '#FF0000') to select."
                    },
                    "x": {
                        "type": "integer",
                        "description": "X coordinate to sample color from."
                    },
                    "y": {
                        "type": "integer",
                        "description": "Y coordinate to sample color from."
                    },
                    "threshold": {
                        "type": "integer",
                        "description": "Color similarity threshold (0-255, default 15)."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "select_all",
            "description": "Selects the entire image canvas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image. Defaults to active image."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "select_none",
            "description": "Clears and removes any active selection from the image.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image. Defaults to active image."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "invert_selection",
            "description": "Inverts the active selection (everything currently unselected becomes selected).",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image. Defaults to active image."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "adjust_brightness_contrast",
            "description": "Adjusts brightness and contrast on a layer or selection. Values range from -100 to 100.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image. Defaults to active image."
                    },
                    "layer_id": {
                        "type": "integer",
                        "description": "Layer ID to modify. Defaults to active layer if omitted."
                    },
                    "brightness": {
                        "type": "number",
                        "description": "Brightness adjustment (-100 to 100, default 0)."
                    },
                    "contrast": {
                        "type": "number",
                        "description": "Contrast adjustment (-100 to 100, default 0)."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "adjust_hue_saturation",
            "description": "Adjusts hue (-180 to 180), lightness (-100 to 100), and saturation (-100 to 100) on a layer or selection.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image. Defaults to active image."
                    },
                    "layer_id": {
                        "type": "integer",
                        "description": "Layer ID to modify. Defaults to active layer if omitted."
                    },
                    "hue": {
                        "type": "number",
                        "description": "Hue shift (-180 to 180)."
                    },
                    "lightness": {
                        "type": "number",
                        "description": "Lightness adjustment (-100 to 100)."
                    },
                    "saturation": {
                        "type": "number",
                        "description": "Saturation adjustment (-100 to 100)."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "adjust_levels",
            "description": "Adjusts tonal levels (input range and gamma) on a layer or selection.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image. Defaults to active image."
                    },
                    "layer_id": {
                        "type": "integer",
                        "description": "Layer ID to modify. Defaults to active layer if omitted."
                    },
                    "channel": {
                        "type": "string",
                        "enum": ["value", "red", "green", "blue", "alpha"],
                        "description": "Channel to adjust (default 'value')."
                    },
                    "low_input": {
                        "type": "number",
                        "description": "Shadow input level (0-255 or 0.0-1.0)."
                    },
                    "high_input": {
                        "type": "number",
                        "description": "Highlight input level (0-255 or 0.0-1.0)."
                    },
                    "gamma": {
                        "type": "number",
                        "description": "Midtone gamma adjustment (default 1.0)."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "desaturate",
            "description": "Converts the layer or selection to grayscale using luminance, lightness, or average mode.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image. Defaults to active image."
                    },
                    "layer_id": {
                        "type": "integer",
                        "description": "Layer ID to modify. Defaults to active layer if omitted."
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["luminance", "luminosity", "lightness", "average"],
                        "description": "Desaturation algorithm mode (default 'luminance')."
                    }
                }
            }
        }
    }
]


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 3: More Color, Filters & Effects (10 Tools)
# ═══════════════════════════════════════════════════════════════════════════════

PHASE3_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "adjust_curves",
            "description": "Applies a tone curve adjustment to a layer using named presets ('s_curve', 'lighten', 'darken', 'increase_contrast').",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image. Defaults to active image."
                    },
                    "layer_id": {
                        "type": "integer",
                        "description": "Layer ID to modify. Defaults to active layer if omitted."
                    },
                    "preset": {
                        "type": "string",
                        "enum": ["s_curve", "lighten", "darken", "increase_contrast", "lift_shadows", "fade_highlights", "linear"],
                        "description": "The curve preset to apply (default 's_curve'). 'lift_shadows' brightens dark tones; 'fade_highlights' softens bright tones; 'increase_contrast' boosts mid-range contrast."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "adjust_color_balance",
            "description": "Adjusts color tint balance across shadows, midtones, or highlights.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image. Defaults to active image."
                    },
                    "layer_id": {
                        "type": "integer",
                        "description": "Layer ID to modify. Defaults to active layer if omitted."
                    },
                    "cyan_red": {
                        "type": "number",
                        "description": "Cyan (-100) to Red (+100) adjustment."
                    },
                    "magenta_green": {
                        "type": "number",
                        "description": "Magenta (-100) to Green (+100) adjustment."
                    },
                    "yellow_blue": {
                        "type": "number",
                        "description": "Yellow (-100) to Blue (+100) adjustment."
                    },
                    "range": {
                        "type": "string",
                        "enum": ["shadows", "midtones", "highlights"],
                        "description": "Tonal range to target (default 'midtones')."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "invert_colors",
            "description": "Inverts the colors of a layer or active selection (creates a negative effect).",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image. Defaults to active image."
                    },
                    "layer_id": {
                        "type": "integer",
                        "description": "Layer ID to modify. Defaults to active layer if omitted."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "apply_gaussian_blur",
            "description": "Applies a smooth Gaussian blur filter to a layer or active selection.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image. Defaults to active image."
                    },
                    "layer_id": {
                        "type": "integer",
                        "description": "Layer ID to modify. Defaults to active layer if omitted."
                    },
                    "radius": {
                        "type": "number",
                        "description": "Blur radius in pixels (default 5.0)."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "apply_motion_blur",
            "description": "Applies a linear motion blur filter along a specified angle and distance.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image. Defaults to active image."
                    },
                    "layer_id": {
                        "type": "integer",
                        "description": "Layer ID to modify. Defaults to active layer if omitted."
                    },
                    "angle": {
                        "type": "number",
                        "description": "Directional motion angle in degrees (default 45.0)."
                    },
                    "length": {
                        "type": "number",
                        "description": "Blur stroke length in pixels (default 10.0)."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "apply_sharpen",
            "description": "Sharpens details in a layer or active selection using unsharp masking.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image. Defaults to active image."
                    },
                    "layer_id": {
                        "type": "integer",
                        "description": "Layer ID to modify. Defaults to active layer if omitted."
                    },
                    "amount": {
                        "type": "number",
                        "description": "Sharpening intensity (0 to 100, default 50)."
                    },
                    "radius": {
                        "type": "number",
                        "description": "Sharpening radius in pixels (default 3.0)."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "apply_pixelize",
            "description": "Applies a pixel art / mosaic block effect to a layer or active selection.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image. Defaults to active image."
                    },
                    "layer_id": {
                        "type": "integer",
                        "description": "Layer ID to modify. Defaults to active layer if omitted."
                    },
                    "block_size": {
                        "type": "integer",
                        "description": "Pixel mosaic block size in pixels (default 10)."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "apply_emboss",
            "description": "Applies a 3D relief embossing filter to a layer or selection.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image. Defaults to active image."
                    },
                    "layer_id": {
                        "type": "integer",
                        "description": "Layer ID to modify. Defaults to active layer if omitted."
                    },
                    "azimuth": {
                        "type": "number",
                        "description": "Light source azimuth angle (default 30.0)."
                    },
                    "elevation": {
                        "type": "number",
                        "description": "Light source elevation angle (default 45.0)."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "apply_noise",
            "description": "Adds RGB grain/noise texture to a layer or selection.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image. Defaults to active image."
                    },
                    "layer_id": {
                        "type": "integer",
                        "description": "Layer ID to modify. Defaults to active layer if omitted."
                    },
                    "amount": {
                        "type": "number",
                        "description": "Noise intensity percentage (0 to 100, default 20)."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "apply_edge_detect",
            "description": "Applies an edge detection filter (Sobel algorithm) to extract outlines.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image. Defaults to active image."
                    },
                    "layer_id": {
                        "type": "integer",
                        "description": "Layer ID to modify. Defaults to active layer if omitted."
                    },
                    "algorithm": {
                        "type": "string",
                        "enum": ["sobel", "prewitt", "gradient"],
                        "description": "Edge detection algorithm (default 'sobel')."
                    }
                }
            }
        }
    }
]


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 4: Layers (8 Tools)
# ═══════════════════════════════════════════════════════════════════════════════

PHASE4_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "add_layer",
            "description": "Creates and inserts a new layer into the image.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image. Defaults to active image."
                    },
                    "name": {
                        "type": "string",
                        "description": "Name for the new layer (default 'New Layer')."
                    },
                    "width": {
                        "type": "integer",
                        "description": "Width of layer (defaults to canvas width)."
                    },
                    "height": {
                        "type": "integer",
                        "description": "Height of layer (defaults to canvas height)."
                    },
                    "fill_type": {
                        "type": "string",
                        "enum": ["transparent", "white", "black", "foreground", "background"],
                        "description": "Initial layer fill color (default 'transparent')."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_layer",
            "description": "Deletes and removes a layer from the image.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image. Defaults to active image."
                    },
                    "layer_id": {
                        "type": "integer",
                        "description": "ID of the layer to delete. Defaults to active layer if omitted."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "duplicate_layer",
            "description": "Duplicates an existing layer into a new layer above it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image. Defaults to active image."
                    },
                    "layer_id": {
                        "type": "integer",
                        "description": "ID of the layer to duplicate. Defaults to active layer if omitted."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "merge_down",
            "description": "Merges the specified layer downward onto the layer directly beneath it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image. Defaults to active image."
                    },
                    "layer_id": {
                        "type": "integer",
                        "description": "ID of the upper layer to merge down. Defaults to active layer if omitted."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "flatten_image",
            "description": "Flattens all visible image layers into a single background layer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image. Defaults to active image."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_layer_opacity",
            "description": "Sets the opacity of a layer (0 to 100).",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image. Defaults to active image."
                    },
                    "layer_id": {
                        "type": "integer",
                        "description": "ID of the layer. Defaults to active layer if omitted."
                    },
                    "opacity": {
                        "type": "number",
                        "description": "Opacity percentage from 0 (completely transparent) to 100 (opaque)."
                    }
                },
                "required": ["opacity"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_layer_blend_mode",
            "description": "Sets the blending mode of a layer (normal, multiply, screen, overlay, difference, etc.).",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image. Defaults to active image."
                    },
                    "layer_id": {
                        "type": "integer",
                        "description": "ID of the layer. Defaults to active layer if omitted."
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["normal", "multiply", "screen", "overlay", "difference", "darken", "lighten", "addition", "subtraction"],
                        "description": "Blend mode to apply."
                    }
                },
                "required": ["mode"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rename_layer",
            "description": "Renames a layer for clarity and identification in later steps.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image. Defaults to active image."
                    },
                    "layer_id": {
                        "type": "integer",
                        "description": "ID of the layer. Defaults to active layer if omitted."
                    },
                    "new_name": {
                        "type": "string",
                        "description": "New name for the layer."
                    }
                },
                "required": ["new_name"]
            }
        }
    }
]


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 5: Text, Drawing & Per-Layer Transforms (12 Tools)
# ═══════════════════════════════════════════════════════════════════════════════

PHASE5_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "add_text_layer",
            "description": "Renders and adds a text string as a new layer with specified font, size, and color.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image. Defaults to active image."
                    },
                    "text": {
                        "type": "string",
                        "description": "The text content to render."
                    },
                    "x": {
                        "type": "integer",
                        "description": "X placement coordinate."
                    },
                    "y": {
                        "type": "integer",
                        "description": "Y placement coordinate."
                    },
                    "font": {
                        "type": "string",
                        "description": "Font family name (e.g. 'Sans-serif', 'Arial', 'Times New Roman')."
                    },
                    "size": {
                        "type": "number",
                        "description": "Font size in pixels (default 24)."
                    },
                    "color": {
                        "type": "string",
                        "description": "Text color name or hex code (e.g. 'black', '#FFFFFF')."
                    }
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "draw_rectangle",
            "description": "Draws a filled or outlined rectangle directly onto the target layer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image. Defaults to active image."
                    },
                    "layer_id": {
                        "type": "integer",
                        "description": "Layer ID to draw on. Defaults to active layer if omitted."
                    },
                    "x": {
                        "type": "integer",
                        "description": "Left coordinate of rectangle."
                    },
                    "y": {
                        "type": "integer",
                        "description": "Top coordinate of rectangle."
                    },
                    "width": {
                        "type": "integer",
                        "description": "Width of rectangle."
                    },
                    "height": {
                        "type": "integer",
                        "description": "Height of rectangle."
                    },
                    "color": {
                        "type": "string",
                        "description": "Fill or stroke color (e.g. 'red', '#00FF00')."
                    },
                    "filled": {
                        "type": "boolean",
                        "description": "True to fill rectangle, False to stroke outline."
                    }
                },
                "required": ["x", "y", "width", "height"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "draw_ellipse",
            "description": "Draws a filled or outlined ellipse directly onto the target layer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image. Defaults to active image."
                    },
                    "layer_id": {
                        "type": "integer",
                        "description": "Layer ID to draw on. Defaults to active layer if omitted."
                    },
                    "x": {
                        "type": "integer",
                        "description": "Left coordinate of bounding box."
                    },
                    "y": {
                        "type": "integer",
                        "description": "Top coordinate of bounding box."
                    },
                    "width": {
                        "type": "integer",
                        "description": "Width of ellipse."
                    },
                    "height": {
                        "type": "integer",
                        "description": "Height of ellipse."
                    },
                    "color": {
                        "type": "string",
                        "description": "Fill or stroke color."
                    },
                    "filled": {
                        "type": "boolean",
                        "description": "True to fill ellipse, False to stroke outline."
                    }
                },
                "required": ["x", "y", "width", "height"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "draw_line",
            "description": "Draws a straight line from (x1, y1) to (x2, y2) with specified color and thickness.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image. Defaults to active image."
                    },
                    "layer_id": {
                        "type": "integer",
                        "description": "Layer ID to draw on. Defaults to active layer if omitted."
                    },
                    "x1": {
                        "type": "number",
                        "description": "Starting X coordinate."
                    },
                    "y1": {
                        "type": "number",
                        "description": "Starting Y coordinate."
                    },
                    "x2": {
                        "type": "number",
                        "description": "Ending X coordinate."
                    },
                    "y2": {
                        "type": "number",
                        "description": "Ending Y coordinate."
                    },
                    "color": {
                        "type": "string",
                        "description": "Line color (e.g. 'blue', '#FF00AA')."
                    },
                    "thickness": {
                        "type": "number",
                        "description": "Line thickness in pixels (default 2.0)."
                    }
                },
                "required": ["x1", "y1", "x2", "y2"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fill_selection",
            "description": "Fills the currently active selection with a solid color on the target layer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image. Defaults to active image."
                    },
                    "layer_id": {
                        "type": "integer",
                        "description": "Layer ID to fill. Defaults to active layer if omitted."
                    },
                    "color": {
                        "type": "string",
                        "description": "Color name or hex string."
                    }
                },
                "required": ["color"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "move_layer",
            "description": "Moves / repositions a layer by offset (x_offset, y_offset) relative to its current placement.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image. Defaults to active image."
                    },
                    "layer_id": {
                        "type": "integer",
                        "description": "Layer ID to move. Defaults to active layer if omitted."
                    },
                    "x_offset": {
                        "type": "integer",
                        "description": "Horizontal pixel shift (positive right, negative left)."
                    },
                    "y_offset": {
                        "type": "integer",
                        "description": "Vertical pixel shift (positive down, negative up)."
                    }
                },
                "required": ["x_offset", "y_offset"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "scale_layer",
            "description": "Resizes a single specific layer without changing canvas dimensions (unlike scale_image).",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image. Defaults to active image."
                    },
                    "layer_id": {
                        "type": "integer",
                        "description": "Layer ID to scale. Defaults to active layer if omitted."
                    },
                    "width": {
                        "type": "integer",
                        "description": "Target width in pixels."
                    },
                    "height": {
                        "type": "integer",
                        "description": "Target height in pixels."
                    }
                },
                "required": ["width", "height"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rotate_layer",
            "description": "Rotates a single specific layer by arbitrary degrees without rotating canvas (unlike rotate_image).",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image. Defaults to active image."
                    },
                    "layer_id": {
                        "type": "integer",
                        "description": "Layer ID to rotate. Defaults to active layer if omitted."
                    },
                    "degrees": {
                        "type": "number",
                        "description": "Rotation angle in degrees."
                    }
                },
                "required": ["degrees"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "reorder_layer",
            "description": "Changes the stacking order of a layer in the layer stack (0 is top-most).",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image. Defaults to active image."
                    },
                    "layer_id": {
                        "type": "integer",
                        "description": "Layer ID to move. Defaults to active layer if omitted."
                    },
                    "new_position": {
                        "type": "integer",
                        "description": "New 0-indexed position in stack."
                    }
                },
                "required": ["new_position"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "feather_selection",
            "description": "Feathers / softens the edge of the currently active selection.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image. Defaults to active image."
                    },
                    "radius": {
                        "type": "number",
                        "description": "Feather radius in pixels (default 5.0)."
                    }
                },
                "required": ["radius"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_foreground_color",
            "description": "Sets the active GIMP foreground brush/fill color. Call this before draw_rectangle, draw_ellipse, draw_line, or fill_selection when you want a specific color.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image (optional — used only to ground the returned image_state)."
                    },
                    "color": {
                        "type": "string",
                        "description": "Color name or hex string (e.g. 'red', '#00FFAA')."
                    }
                },
                "required": ["color"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_layer_info",
            "description": "Queries detailed properties of a specific layer (position, dimensions, opacity, blend mode).",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_id": {
                        "type": "integer",
                        "description": "ID of the image. Defaults to active image."
                    },
                    "layer_id": {
                        "type": "integer",
                        "description": "Layer ID. Defaults to active layer if omitted."
                    }
                }
            }
        }
    }
]
# Core Tools that are always loaded (inspection, loading, exporting)
CORE_TOOLS = [
    PHASE1_SCHEMAS[0],  # load_image
    PHASE1_SCHEMAS[1],  # export_image
    PHASE1_SCHEMAS[4],  # get_image_info
]

TOOL_CATEGORIES = {
    "canvas_and_file": PHASE1_SCHEMAS,
    "selections_and_color": PHASE2_SCHEMAS,
    "filters_and_effects": PHASE3_SCHEMAS,
    "layer_management": PHASE4_SCHEMAS,
    "drawing_and_transforms": PHASE5_SCHEMAS
}

ROUTER_TOOL = {
    "type": "function",
    "function": {
        "name": "request_tool_category",
        "description": "Request tools for one or more specific categories. Core tools (load_image, export_image, get_image_info) are always loaded.",
        "parameters": {
            "type": "object",
            "properties": {
                "category_name": {
                    "type": "string",
                    "enum": list(TOOL_CATEGORIES.keys()),
                    "description": "Category name to load. Choose from: 'canvas_and_file' (resize, scale, crop, rotate, flip), 'selections_and_color' (select shapes/colors, brightness, hue, levels), 'filters_and_effects' (curves, color balance, blur, sharpen, noise, pixelize), 'layer_management' (add, delete, duplicate, merge, opacity, blend modes), 'drawing_and_transforms' (text, draw shapes, fill, move/scale/rotate layer, foreground color)."
                },
                "additional_categories": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": list(TOOL_CATEGORIES.keys())
                    },
                    "description": "Optional additional categories to load simultaneously for multi-step tasks (e.g. ['selections_and_color', 'filters_and_effects'])."
                }
            },
            "required": ["category_name"]
        }
    }
}


def get_all_tools():
    """Returns the aggregated list of all registered tool schemas across all 5 phases (50 tools total)."""
    return PHASE1_SCHEMAS + PHASE2_SCHEMAS + PHASE3_SCHEMAS + PHASE4_SCHEMAS + PHASE5_SCHEMAS


def get_category_tools(category_names, current_tools=None, accumulate=True):
    """
    Returns tool schemas for the requested category or list of categories.
    Ensures CORE_TOOLS and ROUTER_TOOL are always included.
    If accumulate=True and current_tools is provided, merges them without duplicates.
    """
    if isinstance(category_names, str):
        requested_cats = [category_names]
    elif isinstance(category_names, (list, tuple)):
        requested_cats = list(category_names)
    else:
        requested_cats = []

    tools_dict = {}

    # 1. Base / Core tools always present
    for t in CORE_TOOLS:
        name = t["function"]["name"]
        tools_dict[name] = t

    # 2. Existing tools if accumulating
    if accumulate and current_tools:
        for t in current_tools:
            name = t["function"]["name"]
            if name != "request_tool_category":
                tools_dict[name] = t

    # 3. New categories requested
    for cat in requested_cats:
        for t in TOOL_CATEGORIES.get(cat, []):
            name = t["function"]["name"]
            tools_dict[name] = t

    # 4. Router tool always present
    tools_dict["request_tool_category"] = ROUTER_TOOL

    return list(tools_dict.values())



