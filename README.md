# 🎨 GIMP Agentic AI — Natural Language Image Editor

A local, chat-driven agentic AI interface for **GIMP 3.2.4+**. Control GIMP using natural language instructions through a local LLM (Ollama) or cloud models (Google Gemini, OpenAI GPT-4o). The AI agent translates your intent into atomic tool calls executed against an in-GIMP socket server with real-time visual canvas updates.

---

## 📑 Table of Contents
- [🌟 Key Features](#-key-features)
- [📋 Prerequisites](#-prerequisites)
- [📦 Installation Guide](#-installation-guide)
- [🚀 Quick Start / User Manual](#-quick-start--user-manual)
- [💡 Example Workflows & Prompt Cookbook](#-example-workflows--prompt-cookbook)
- [🛠️ Tool Capabilities Reference (50 Tools)](#️-tool-capabilities-reference-50-tools)
- [📡 Socket Protocol Specification](#-socket-protocol-specification)
- [🧪 Verification & Testing](#-verification--testing)

---

## 🌟 Key Features

- **50 Implemented Native GIMP Tools**: Full control over canvas geometry, selections, color grading, GEGL filters, layer stack management, shape drawing, and text layers.
- **Main-Thread Safe**: All GIMP API and GEGL operations run safely via `GLib.idle_add()` on the GIMP main UI thread, eliminating Windows GTK multi-threading crashes.
- **Single-Step Undo UX**: Every agent action is wrapped in an `undo_group_start/end` block so `Ctrl+Z` cleanly reverts complete operations in one stroke.
- **Real-Time Visual Sync**: Displays automatically flush (`Gimp.displays_flush()`) on every edit so you see the canvas change live.
- **State Grounding & Self-Correction**: Every tool response returns the live `image_state` (dimensions, layer stack, active layer ID), allowing the LLM to verify and self-correct.
- **Category Routing**: Dynamically loads tools by category, reducing context window token overhead from ~4,500 tokens down to ~900 tokens per turn.
- **Multi-LLM Support**: Pluggable architecture supporting local Ollama (`qwen2.5:3b`, `llama3.2`, etc.), Google Gemini (`gemini-2.5-flash`, `gemini-1.5-pro`), and OpenAI (`gpt-4o`).

---

## 📋 Prerequisites

1. **GIMP 3.2.4 or newer**: [Download GIMP 3.2](https://www.gimp.org/downloads/)
2. **Python 3.10+**: Standard Python installation (or the Python bundled with GIMP 3.2 at `C:\Program Files\GIMP 3\bin\python.exe`).
3. **LLM Backend** (Choose at least one):
   - **Local**: [Ollama](https://ollama.com/) with `qwen2.5:3b` installed (`ollama pull qwen2.5:3b`).
   - **Cloud**: Google Gemini API key (`GEMINI_API_KEY`) or OpenAI API key (`OPENAI_API_KEY`).

---

## 📦 Installation Guide

### Step 1: Clone or Download this Repository
```bash
git clone <your-repository-url>
cd AI_Image_edit
```

### Step 2: Install the GIMP Plugin
Copy the `gimp_agent_plugin` folder into your GIMP 3.2 user plug-ins directory.

**Windows Directory Path:**
```
%APPDATA%\GIMP\3.2\plug-ins\gimp_agent_plugin\
```
*(Full path typically: `C:\Users\<YourUsername>\AppData\Roaming\GIMP\3.2\plug-ins\gimp_agent_plugin\`)*

**Verify the folder structure:**
```
%APPDATA%\GIMP\3.2\plug-ins\
└── gimp_agent_plugin\
    └── gimp_agent_plugin.py
```

> **Important:** The directory name (`gimp_agent_plugin`) must match the script base name (`gimp_agent_plugin.py`) for GIMP 3.x GObject Introspection plugins to register.

### Step 3: (Optional) Install Python Dependencies
The core client uses Python's standard library (`socket`, `json`, `urllib`) for zero-dependency baseline. If you wish to install the requirements:
```bash
pip install -r requirements.txt
```

---

## 🚀 Quick Start / User Manual

### Step 1: Start the GIMP Server
1. Launch **GIMP 3.2**.
2. From the top menu bar, select:
   **`Tools` > `AI Agent` > `Start AI Agent Server`**
3. A non-blocking background server will start listening on `localhost:9877`. You can continue using the GIMP UI normally.

### Step 2: Launch the AI CLI

Choose your LLM engine:

#### 1. Local Ollama (Default — Qwen2.5-3B)
Ensure Ollama is running in the background, then launch:
```bash
python cli.py
```
To run with a larger local model:
```bash
python cli.py ollama qwen2.5:7b
```

#### 2. Google Gemini
Set your API key and start the CLI:
```bash
# Windows Command Prompt
set GEMINI_API_KEY=your_gemini_api_key_here
python cli.py gemini

# Windows PowerShell
$env:GEMINI_API_KEY="your_gemini_api_key_here"
python cli.py gemini
```

#### 3. OpenAI GPT-4o
```bash
# Windows Command Prompt
set OPENAI_API_KEY=your_openai_api_key_here
python cli.py openai gpt-4o

# Windows PowerShell
$env:OPENAI_API_KEY="your_openai_api_key_here"
python cli.py openai gpt-4o
```

#### Tool Context Modes:
- **Category Routing (Default)**: Token-efficient dynamic tool loading. Best for 3B/7B local models.
- **Direct Mode (`--all-tools`)**: Loads all 50 tools upfront. Recommended for large models like Gemini 2.5 Flash / GPT-4o:
  ```bash
  python cli.py gemini --all-tools
  ```

---

## 💡 Example Workflows & Prompt Cookbook

### Workflow 1: Quick Canvas Enhancement
*Open an image in GIMP (`File > Open`), then type in the CLI:*
```
gimp-ai > Inspect the image and give me its dimensions and layer names.
gimp-ai > Increase brightness by 15% and midtone contrast by 10%.
gimp-ai > Apply an s_curve tone preset to give it richer depth.
```

### Workflow 2: File-to-File Batch Transformation
*Start with an empty GIMP workspace:*
```
gimp-ai > Open C:\photos\portrait.jpg, scale the image to 1920x1080 maintaining aspect ratio, convert it to black and white, and export it as C:\photos\portrait_bw.png
```

### Workflow 3: Region Selection & Filter Chaining
*Select specific parts of the image to apply localized adjustments:*
```
gimp-ai > Select a rectangle in the center (x:200, y:150, width:600, height:400), apply gaussian blur with radius 12, then invert the selection and desaturate the background. Finally clear the selection.
```

### Workflow 4: Social Media Banner / Multi-Layer Design
```
gimp-ai > Add a semi-transparent dark rectangle overlay at the bottom (x:0, y:800, width:1920, height:280) with opacity 0.6.
gimp-ai > Add a text layer saying 'NEW RELEASE' in bold white with font size 64 positioned at (100, 850).
gimp-ai > Duplicate the text layer, rename it to 'Shadow', set color to black, and move it to (103, 853) below the original text.
```

### Interactive CLI Session Commands
- `reset` or `clear`: Clears conversation history and restores active tools to a clean baseline state.
- `exit`, `quit`, or `q`: Exits the agent session.

---

## 🛠️ Tool Capabilities Reference (50 Tools)

All 50 tools are fully implemented and grouped into 5 categories:

### 1. Canvas & File Management
- `load_image`: Open an image from disk into GIMP.
- `export_image`: Flatten and save the image to disk (`.png`, `.jpg`, `.webp`).
- `duplicate_image`: Clone open image to a new canvas.
- `close_image`: Close image and free memory.
- `get_image_info`: Inspect canvas dimensions, layers, active layer ID.
- `resize_image`: Expand or shrink canvas boundaries.
- `scale_image`: Proportionally resize canvas and all layers.
- `crop_image`: Crop canvas to rectangle boundary.
- `rotate_image`: Rotate entire canvas (90°, 180°, 270°).
- `flip_image`: Flip canvas horizontally or vertically.

### 2. Selections & Color Grading
- `select_rectangle`: Select rectangular bounding box.
- `select_ellipse`: Select elliptical / circular region.
- `select_by_color`: Select contiguous areas matching a color.
- `select_all` / `select_none` / `invert_selection`: Selection boundary controls.
- `adjust_brightness_contrast`: Simple brightness and contrast sliders.
- `adjust_hue_saturation`: Color hue rotation, lightness, saturation.
- `adjust_levels`: Black/white point and gamma adjustment.
- `desaturate`: Convert to greyscale (luminosity, average, value).

### 3. Filters & Effects (GEGL)
- `adjust_curves`: Spline tonal curves (`s_curve`, `lighten`, `darken`, `increase_contrast`, `lift_shadows`, `fade_highlights`).
- `adjust_color_balance`: Fine-tune shadows, midtones, highlights across Cyan-Red, Magenta-Green, Yellow-Blue.
- `invert_colors`: Photonegative RGB color inversion.
- `apply_gaussian_blur`: Smooth gaussian blur.
- `apply_motion_blur`: Linear directional motion blur.
- `apply_sharpen`: Unsharp mask sharpening.
- `apply_pixelize`: Pixelation block effect.
- `apply_emboss`: 3D embossed relief lighting.
- `apply_noise`: RGB noise generator.
- `apply_edge_detect`: Sobel edge detection.

### 4. Layer Management
- `add_layer`: Create transparent, white, or colored layer.
- `delete_layer`: Remove a specific layer.
- `duplicate_layer`: Clone layer with exact dimensions and pixels.
- `merge_down`: Merge layer into the layer below.
- `flatten_image`: Flatten all layers into a single background.
- `set_layer_opacity`: Set transparency (0.0 to 1.0).
- `set_layer_blend_mode`: Set blend mode (`normal`, `multiply`, `screen`, `overlay`, etc.).
- `rename_layer`: Rename layer in GIMP layer stack.

### 5. Drawing, Text & Transforms
- `add_text_layer`: Render crisp typography with custom font, size, color.
- `draw_rectangle` / `draw_ellipse` / `draw_line`: Vector-stroked shapes.
- `fill_selection`: Flood fill selection with foreground color or pattern.
- `move_layer`: Translate layer coordinates `(x, y)` on canvas.
- `scale_layer`: Resize individual layer independently of canvas.
- `rotate_layer`: Rotate single layer around center.
- `reorder_layer`: Move layer up/down in stack hierarchy.
- `feather_selection`: Soften selection borders.
- `set_foreground_color`: Set active brush/paint color.
- `get_layer_info`: Query layer position, dimensions, opacity, blend mode.

---

## 📡 Socket Protocol Specification

The client and in-GIMP plugin communicate over TCP `localhost:9877` using newline-delimited JSON (`\n`).

### Request Format:
```json
{
  "tool": "adjust_brightness_contrast",
  "arguments": {
    "image_id": 1,
    "layer_id": 2,
    "brightness": 0.2,
    "contrast": 0.1
  }
}
```

### Success Response Format:
```json
{
  "status": "success",
  "message": "Adjusted brightness (+0.20) and contrast (+0.10)",
  "image_state": {
    "image_id": 1,
    "width": 1920,
    "height": 1080,
    "active_layer_id": 2,
    "layers": [
      {"id": 2, "name": "Background", "visible": true, "opacity": 1.0}
    ]
  }
}
```

### Error Response Format:
```json
{
  "status": "error",
  "error_type": "LayerNotFoundError",
  "message": "Target layer 99 does not exist",
  "image_state": { ... }
}
```

---

## 🧪 Verification & Testing

Run the deterministic test suite to verify socket communication and tools directly against GIMP without needing an LLM:
```bash
python tools/test_socket_raw.py
```
