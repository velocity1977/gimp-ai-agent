# GIMP Agentic AI — Build Prompt for Gemini

---

## PART 1: Reference Plan (quick overview before the full prompt)

**Goal:** A local, chat-driven image editor. User types a request in natural language; a small local LLM (via Ollama) picks from a library of **50 atomic GIMP tools** and calls them in sequence to accomplish the task.

**Architecture (3 layers)**

1. **GIMP execution layer** — a fork of the existing open-source **maorcc/gimp-mcp** project (a GIMP 3.2 plugin with a built-in persistent socket server), extended with 50 dispatch handlers covering file I/O, canvas geometry, selections, color adjustments, filters, layers, drawing, and per-layer transforms — built and validated in 5 phases of ~10 tools each.
2. **Tool interface layer** — each of the 50 handlers exposed as a JSON tool schema (name, description, params) in Ollama's `tools` format, organized by the same 5 phase-categories.
3. **Orchestration layer** — Python orchestrator: takes user message → sends to Ollama with tool list → model returns tool call(s) → orchestrator executes against the GIMP socket → result fed back to model → loop until done → summary to user.

**Stack**
- GIMP 3.2.4 — native Python 3 / GObject Introspection Python-Fu (not the old `gimpfu` 2.10 API — see Part 2, Section 0)
- A fork of **maorcc/gimp-mcp** opens a persistent in-GIMP socket server (main-thread-safe, see Section 0b) so the image/session stays alive across tool calls
- Ollama running Qwen2.5-3B-Instruct (or 7B if 3B proves unreliable) with native `tools` support
- Python orchestrator (single process, manages both the Ollama client and the GIMP socket client)
- Simple CLI or minimal web chat UI as the interface

**Build order**
1. Confirm exact GIMP 3.2.4 install and the actual Windows plugin directory on this machine
2. Fork maorcc/gimp-mcp, review its socket handler for main-thread safety (fix if needed), confirm its existing socket round-trip works unmodified on Windows
3. Extend it with the 50 tools in 5 phases (~10 tools/phase), testing each phase via a standalone raw-socket smoke-test script (no LLM involved) before the next phase
4. Wrap all 50 tools as Ollama tool schemas
5. Build orchestrator loop (single tool call working end to end)
6. Extend to multi-step chains, including chains that mix tools from different phases
7. Add chat interface (CLI first, web later if wanted)

---

## PART 2: Full Build Prompt (paste this to Gemini)

You are building a local, chat-driven agentic AI interface for GIMP image editing. Read this entire spec before writing any code — several decisions below are load-bearing and changing them later means rework.

### 0. Version target (confirmed — do not deviate)

**Target GIMP 3.2.4.** This is a confirmed constraint, not a default — the API is meaningfully different from GIMP 2.10 and older tutorials/examples targeting 2.10 (`gimpfu`, `gimp.pdb.*`, flat function-style scripts) will not work. Key facts about the 3.x scripting model:

- Python-Fu in GIMP 3.x is **pure Python 3 via GObject Introspection (GI)**, not the old `gimpfu` module (which does not exist in 3.0+).
- Every script starts with:
  ```python
  import gi
  gi.require_version('Gimp', '3.0')
  from gi.repository import Gimp
  gi.require_version('GimpUi', '3.0')
  from gi.repository import GimpUi, GObject, GLib, Gio
  ```
- Plugins are **classes subclassing `Gimp.PlugIn`**, implementing `do_query_procedures`, `do_create_procedure`, and a `run()` method — not flat/procedural scripts like 2.10 GimpFu plugins.
- PDB calls use namespaced GI-style objects, e.g. `Gimp.Image.select_ellipse(image, ...)`, `Gimp.Drawable.edit_fill(drawable, ...)`, `Gimp.Selection.none(image)`, `Gimp.displays_flush()` — not `pdb.gimp_*` shorthand.
- Headless/batch invocation uses `--batch-interpreter=python-fu-eval`, e.g.:
  ```
  gimp-3.0 --no-interface --batch-interpreter python-fu-eval --batch "<python code>" --batch "pdb.gimp_quit(0)"
  ```
- **Base to fork, not build from scratch:** use **maorcc/gimp-mcp** (github.com/maorcc/gimp-mcp) as the starting point. It explicitly targets GIMP 3.2 (matches the installed 3.2.4), already solves the persistent-session problem — a plugin (`gimp-mcp-plugin.py` / `gimp_mcp_server.py`) that opens a socket server inside GIMP on `localhost:9877`, keeping a persistent Python-Fu context alive across calls (image stays loaded in memory, imports/variables persist) — and already handles the annoying version-upgrade path issue (GIMP's per-user plugin directory is versioned, e.g. `~/.config/GIMP/3.2/plug-ins/`, and moves on every minor upgrade). Clone it, get its existing socket round-trip working first (Section 1, Step 1 below), *then* extend its dispatch table with the 50 tools in this spec, rather than writing a socket server from first principles.
  - Note there are several similar independent projects (martinduartemore/mcp-gimp, mstampfer/gimp-mcp-gateway, Shriinivas/gimpmcp, libreearth/gimp-mcp) — maorcc/gimp-mcp is the recommended pick for its explicit 3.2 targeting, but if in practice its plugin fails to load or its protocol proves awkward, martinduartemore/mcp-gimp is the fallback (it also ships a GIMP-3-API stub generator, useful for avoiding hallucinated method names).
- The `gimpfu`-style GimpFu-v3 compatibility shim exists but is unofficial/community-maintained, not supported by gimp.org. Do not use it — the reference repo above and this spec both write against the native `Gimp.PlugIn` / GI API directly, which stays correct for the installed 3.2.4 and doesn't depend on an unofficial shim's maintenance status.

Confirm this understanding at the start of your response before writing code, and flag immediately if you find, while implementing, that any specific PDB call name/signature differs from what's assumed here — GIMP 3.x's GI bindings are newer and less densely documented than 2.10's, so some trial-and-error against the actual installed `Gimp` namespace (via the Python-Fu console) should be expected and is fine.

### 0a. Platform target — Windows (confirmed)

The development environment is **Windows**, not Linux. This changes several assumptions:
- GIMP 3.2's per-user plugin directory on Windows is `%APPDATA%\GIMP\3.2\plug-ins\<plugin-folder>\<plugin-file>.py` (confirm exact path by checking Edit > Preferences > Folders > Plug-ins inside the actual running GIMP instance — do not assume the version-number subfolder without verifying against what's actually installed).
- GIMP 3.x on Windows runs Python plugins inside GIMP's **bundled MSYS2/MinGW Python environment**, not the system Python. Any dependency the in-GIMP plugin code uses must be either Python standard library only (`socket`, `json`, `sys`, `os`, `threading`) or confirmed available inside that bundled interpreter. Do not assume `pip install`-able packages are available to the in-GIMP side — the *external* orchestrator/client side (running as normal system Python) has no such restriction.
- Verify these two things concretely as an early step, before extending the forked plugin: (1) the exact plugin directory path on this machine, (2) that the forked maorcc/gimp-mcp plugin actually loads and its existing socket server starts without errors on Windows, since the upstream repo's primary documented/tested path may lean Linux/macOS.

### 0b. Main-thread / event-loop safety (critical — read before writing the socket handler)

GIMP 3.x's `Gimp.*` PDB calls are built on GTK3/GEGL and are **not thread-safe** — they must run on GIMP's main UI/event-loop thread. If the socket server accepts connections on a background `threading.Thread` and calls `Gimp.Image.*` / `Gimp.Drawable.*` directly from that thread when a message arrives, this risks crashes or race conditions, not just logical bugs.

Required pattern: the socket listener thread should **not** execute GIMP API calls directly. Instead, when a command arrives, it should queue the work and dispatch actual execution onto the main thread via `GLib.idle_add()` (or `GLib.timeout_add()`), then block/wait on a response event until that main-thread execution completes and has a result, before writing the response back to the socket.

**First verification step when forking maorcc/gimp-mcp:** check whether its existing socket handler already does this correctly. Don't assume it does — confirm by reading its dispatch code, and if it calls `Gimp.*` directly from the accept-thread, fix that before adding any of the 50 new tool handlers, since every one of them would inherit the same crash risk.

### 0c. Color parameters are `Gegl.Color`, not RGB tuples

In GIMP 3.x, color-accepting procedures take `Gegl.Color` objects, not plain `(r, g, b)` tuples the way some 2.10-era examples show. Any tool with a `color` param (`draw_rectangle`, `draw_ellipse`, `draw_line`, `fill_selection`, `set_foreground_color`, `add_text_layer`) needs to go through one shared helper — write `parse_color_to_gegl(color_str)` once, centrally, that accepts hex (`#FF0000`), a named color, or an RGBA array, and returns a proper `Gegl.Color`. Do not reimplement color parsing per-tool.

### 0d. Image-level vs. drawable-level targeting

Many PDB operations (color adjustments, filters like blur/sharpen/invert) act on a **drawable** (a layer or mask), not the top-level image, even though it's natural to think of them as "image operations." For every tool where this distinction applies (all of Phase 2 and Phase 3's color/filter tools, in particular), the handler should:
- Accept an optional `layer_id` param
- If `layer_id` is provided, resolve and operate on that specific layer/drawable
- If omitted, default to `Gimp.Image.get_active_layer(image)` (or the equivalent current GI call) rather than requiring the model to always know and pass a layer id

Update the tool schema `description` fields for these tools to state this fallback explicitly (e.g. *"Layer ID to modify. Defaults to the active layer if omitted."*) — this also reduces the chance of a small model failing a call just because it didn't track a layer id from an earlier `get_image_info` response.

### 0e. Undo grouping and canvas sync

Two small additions that matter for anyone actually watching the GIMP GUI while the agent works:
- Wrap every tool execution handler's GIMP-side work in `Gimp.Image.undo_group_start(image)` / `Gimp.Image.undo_group_end(image)`, so each atomic tool call collapses to **one** undo step in GIMP's UI instead of many, and a user manually pressing Ctrl+Z isn't surprised by internal sub-steps.
- Call `Gimp.displays_flush()` at the end of every successful modifying dispatch handler so the GIMP window (if open/visible) immediately reflects the change rather than appearing stale until some other event triggers a redraw.

### 1. Execution layer — GIMP scripts

Requirements:
- Use Python-Fu (native GIMP 3.0 GI-based API — see Section 0) for all tool scripts — easier to maintain and matches the orchestrator language.
- Each tool is **one atomic operation** (a function/method, not necessarily a separately-registered GIMP plugin each — see server pattern below). Do not build composite/multi-step tools.
- Every operation must validate its own inputs (file exists, param ranges, layer exists) and return a **structured JSON result** — never rely on the calling model to have passed correct data.
- Every operation's response should include current image state after it runs (dimensions, layer count, active layer name, file path) so the model has grounding for its next decision.

**Persistent session architecture:** Do not relaunch GIMP per tool call. Fork **maorcc/gimp-mcp** (see Section 0) and extend it rather than building the socket server from scratch:
1. Its GIMP plugin (a `Gimp.PlugIn` subclass) already opens a local TCP socket server (`localhost:9877`) when invoked from within a running GIMP instance.
2. This in-GIMP socket server already keeps a **persistent Python execution context** — receives JSON commands (`{"type": "...", "params": {...}}` in its existing protocol), executes them against the live GIMP session (image stays loaded across calls), and returns a JSON result over the same socket.
3. The 50 atomic tools in the table below are implemented as **dispatch handlers added to this plugin's existing command table**, not as 50 separate GIMP plugins.
4. Your Python orchestrator (Section 3) is the **external client** — it connects to this socket, sends JSON commands, and parses JSON results.

Document exactly how you installed and started the forked plugin (Windows plugin path per Section 0a — confirm the actual path on this machine rather than assuming it), and the exact socket protocol as extended (message framing, host/port, request/response shape, and any new fields added beyond the upstream repo's protocol).

**Standardize the response protocol across all 50 tools, including errors:**
- Success: include the post-operation image/layer state (dimensions, layer count, active layer, relevant ids) as described earlier in this section.
- Error: use a consistent shape — `{"status": "error", "error_type": "...", "message": "...", "image_state": {...}}` — always including current `image_state` even on failure. This lets the orchestrating model see what actually happened and self-correct (e.g. retry with a valid layer id) instead of just getting an opaque failure with no grounding for its next move.

**Build this tool set in five phases, 10 tools per phase, validating each phase against the live GIMP session before starting the next.** This keeps failures isolated to one category at a time rather than debugging 50 handlers at once.

### Phase 1 — Session, File I/O & Canvas Geometry (10)

| Tool name | Params | Purpose |
|---|---|---|
| `load_image` | `path` | Open an image, return image id + metadata |
| `export_image` | `image_id`, `path`, `format` | Flatten and export to file |
| `duplicate_image` | `image_id` | Copy the current image to a new id (safe experimentation) |
| `close_image` | `image_id` | Free an image from memory |
| `get_image_info` | `image_id` | Return current state (dims, layers, mode) — the "check before acting" tool |
| `resize_image` | `image_id`, `width`, `height` | Resize canvas (crop/pad, no content scaling) |
| `scale_image` | `image_id`, `percent` | Scale image content + canvas together |
| `crop_image` | `image_id`, `x`, `y`, `width`, `height` | Crop to region |
| `rotate_image` | `image_id`, `degrees` | Rotate whole image (90/180/270 or arbitrary) |
| `flip_image` | `image_id`, `axis` | Flip horizontal or vertical |

### Phase 2 — Selections & Color Adjustments (10)

| Tool name | Params | Purpose |
|---|---|---|
| `select_rectangle` | `image_id`, `x`, `y`, `width`, `height` | Rectangular selection |
| `select_ellipse` | `image_id`, `x`, `y`, `width`, `height` | Elliptical selection |
| `select_by_color` | `image_id`, `x`, `y`, `threshold` | Fuzzy/color-based selection — groundwork for background isolation |
| `select_all` | `image_id` | Select entire canvas |
| `select_none` | `image_id` | Clear selection |
| `invert_selection` | `image_id` | Invert current selection |
| `adjust_brightness_contrast` | `image_id`, `brightness`, `contrast` | Standard adjustment |
| `adjust_hue_saturation` | `image_id`, `hue`, `lightness`, `saturation` | Standard adjustment |
| `adjust_levels` | `image_id`, `channel`, `low_input`, `high_input`, `gamma` | Tonal range adjustment |
| `desaturate` | `image_id`, `mode` | Grayscale conversion (luminosity/average/etc.) |

### Phase 3 — More Color, Filters & Effects (10)

| Tool name | Params | Purpose |
|---|---|---|
| `adjust_curves` | `image_id`, `layer_id` (optional), `preset` | Curve-based tonal adjustment — use a small set of named presets (e.g. `"s_curve"`, `"lift_shadows"`, `"increase_contrast"`) rather than raw control-point lists; see note below |
| `adjust_color_balance` | `image_id`, `cyan_red`, `magenta_green`, `yellow_blue` | Shadow/midtone/highlight color balance |
| `invert_colors` | `image_id` | Negative/invert |
| `apply_gaussian_blur` | `image_id`, `radius` | Blur |
| `apply_motion_blur` | `image_id`, `angle`, `length` | Directional blur |
| `apply_sharpen` | `image_id`, `amount` | Sharpen |
| `apply_pixelize` | `image_id`, `block_size` | Pixelation/mosaic |
| `apply_emboss` | `image_id`, `azimuth`, `elevation` | Emboss effect |
| `apply_noise` | `image_id`, `amount` | Add noise/grain |
| `apply_edge_detect` | `image_id`, `algorithm` | Edge-detection filter |

### Phase 4 — Layers (8)

| Tool name | Params | Purpose |
|---|---|---|
| `add_layer` | `image_id`, `name`, `width`, `height` | New blank layer |
| `delete_layer` | `image_id`, `layer_id` | Remove a layer |
| `duplicate_layer` | `image_id`, `layer_id` | Copy a layer |
| `merge_down` | `image_id`, `layer_id` | Merge a layer onto the one below |
| `flatten_image` | `image_id` | Flatten all layers to one |
| `set_layer_opacity` | `image_id`, `layer_id`, `opacity` | Layer opacity 0-100 |
| `set_layer_blend_mode` | `image_id`, `layer_id`, `mode` | Blend mode (normal/multiply/screen/etc.) |
| `rename_layer` | `image_id`, `layer_id`, `new_name` | Rename for clarity in later calls |

### Phase 5 — Text, Drawing & Per-Layer Transforms (12)

| Tool name | Params | Purpose |
|---|---|---|
| `add_text_layer` | `image_id`, `text`, `x`, `y`, `font`, `size`, `color` | Add text as a new layer |
| `draw_rectangle` | `image_id`, `x`, `y`, `width`, `height`, `color`, `filled` | Draw a rectangle onto the active layer |
| `draw_ellipse` | `image_id`, `x`, `y`, `width`, `height`, `color`, `filled` | Draw an ellipse onto the active layer |
| `draw_line` | `image_id`, `x1`, `y1`, `x2`, `y2`, `color`, `thickness` | Draw a line |
| `fill_selection` | `image_id`, `color` | Fill current selection with a solid color |
| `move_layer` | `image_id`, `layer_id`, `x_offset`, `y_offset` | Reposition a layer |
| `scale_layer` | `image_id`, `layer_id`, `width`, `height` | Resize a single layer (not the canvas) |
| `rotate_layer` | `image_id`, `layer_id`, `degrees` | Rotate a single layer |
| `reorder_layer` | `image_id`, `layer_id`, `new_position` | Change stacking order |
| `feather_selection` | `image_id`, `radius` | Soften selection edges |
| `set_foreground_color` | `color` | Set the active drawing color for subsequent fill/draw calls |
| `get_layer_info` | `image_id`, `layer_id` | Return a single layer's state (position, size, opacity, mode) |

**Tool-schema description discipline at this scale matters more, not less.** With 50 tools instead of 10, small-model confusion between semantically-close tools (e.g. `crop_image` vs `select_rectangle`, `scale_image` vs `scale_layer`, `rotate_image` vs `rotate_layer`) becomes the primary failure mode. Section 2 below covers this — write descriptions that explicitly disambiguate image-level vs. layer-level and vs. selection-level operations, since that's the axis most likely to trip up a 3B model.

**Note on `adjust_curves`:** don't expose raw arbitrary control-point lists (e.g. `[[x1,y1],[x2,y2],...]`) as a tool parameter — nested/variable-length structured params are a common source of malformed tool calls from smaller models. Offer a small fixed set of named presets instead (`s_curve`, `lift_shadows`, `increase_contrast`, etc.), each mapping internally to a known-good control-point curve. This trades some flexibility for a large reliability gain at 3-7B scale; if genuinely arbitrary curve control turns out to be needed later, that's a good candidate for a separate, more advanced tool rather than complicating this one.

### 2. Tool schema layer

- Express each of the 50 tools as an Ollama-compatible tool definition (OpenAI-style function-calling JSON: `name`, `description`, `parameters` as JSON schema with typed properties, required fields marked).
- Tool `description` fields matter more at 50 tools than they did at 10 — be explicit and unambiguous, especially across the image-vs-layer-vs-selection axis called out in Phase 5 above (e.g. `scale_image` vs `scale_layer`, `rotate_image` vs `rotate_layer`).
- For every layer-dependent tool, make `layer_id` **optional** in the schema, with a description explicitly stating the fallback: *"Layer ID to modify. Defaults to the active layer if omitted."* (see Section 0d). This meaningfully reduces failed calls from a model that hasn't tracked a specific layer id.
- Consider whether all 50 tools need to be in every request's tool list — this isn't just a nice-to-have at this scale: 50 full tool schemas is roughly 3,000-4,500 tokens of overhead on every single call, and at that count qwen2.5:3b specifically becomes prone to hallucinated parameter names, wrong tool selection, or dropped tool calls. Two options worth evaluating once Phase 1-2 are working: (a) a lightweight category router — model first picks a category (geometry/color/filter/layer/draw), then a second call gets only that category's tools; (b) send all 50 and rely on strong descriptions, measuring actual accuracy before adding routing complexity. Given the token-overhead math above, don't treat (b) as a safe default to stick with indefinitely — budget real time in early testing (small 2-3-category bundles first, before full 50-tool prompts) to check whether (a) is needed sooner than "only if logs show confusion."
- Store tool schemas separately from the GIMP script implementations (e.g. `tools/schema.py`, organized by the same five phase-categories used above) so schemas can be iterated without touching execution code.

### 3. Orchestration layer

- Python process that:
  1. Holds conversation history
  2. Sends user message + tool list to Ollama (`qwen2.5:3b`, or size TBD — see Section 5)
  3. Parses tool call(s) from response
  4. Executes against the GIMP socket, collects structured result
  5. Feeds result back to the model as a tool response message
  6. Loops until the model returns a final natural-language answer (no more tool calls)
- Cap the loop (e.g. max 10 tool calls per user turn) to prevent runaway chains from a confused model.
- Log every tool call + result to a local file — this is essential for debugging small-model routing errors and deciding whether to size up the model later.

### 4. Chat interface

Start with a **CLI loop** (stdin/stdout) — this is sufficient to validate the whole pipeline and is much faster to build than a web UI. Only build a minimal web chat interface (simple Flask/FastAPI + single HTML page) if the user explicitly asks for it after the CLI version works. Do not build both up front.

### 5. Model choice

Start with **Qwen2.5-3B-Instruct** via Ollama's native `tools` parameter, but test it specifically against the **50-tool** list, not just a handful — routing accuracy degrades as the candidate tool count grows, and 50 semantically-adjacent tools (see the image/layer/selection disambiguation note in Phase 5 and Section 2) is a meaningfully harder routing problem than the original 10-tool set this architecture was first validated against. If tool-call logs show frequent wrong-tool-selection or malformed args once real testing starts, step up to **Qwen2.5-7B-Instruct** first (same Ollama API, config-only change). If accuracy is still poor at 7B specifically *because of* tool-list size (not just general capability), that's the signal to build the category-router option described in Section 2 rather than continuing to size up the model.

### 6. Explicitly out of scope for this build

Do not implement any of the following unless separately requested:
- Video editing (separate tool, separate project, not this one)
- Background removal / masking beyond the basic `select_by_color` groundwork tool
- Web UI (unless requested after CLI validation)
- Multi-user or authentication concerns
- GBNF/raw llama.cpp grammar constraints (only revisit if Ollama's native tool-calling proves insufficient)

### 7. Deliverables, in order

1. A written confirmation of the GIMP 3.2.4 API understanding (Section 0, including the Windows path/environment specifics in 0a) before any code
2. A working fork of **maorcc/gimp-mcp**, with its existing socket handling reviewed against the main-thread-safety requirement in Section 0b (fixed if it isn't already correct), and its existing socket round-trip confirmed working unmodified on the actual Windows plugin directory before any new tools are added
3. `tools/test_socket_raw.py` — a standalone smoke-test script that sends raw JSON commands directly to the GIMP socket, independent of Ollama/the orchestrator entirely. Build and use this from Phase 1 onward — it's what makes each phase's tools testable deterministically without LLM non-determinism in the loop, and should exist before Phase 1's tools do, not be added later
4. The forked plugin extended with all 50 dispatch handlers, added and validated **in the five phases defined above**, each phase's tools tested via `test_socket_raw.py` before moving to the next phase, each handler following the shared conventions from Section 0 (undo grouping, `Gimp.displays_flush()`, `parse_color_to_gegl` helper for color params, active-layer fallback, standardized error response shape)
5. `tools/socket_client.py` — the client used by the orchestrator (distinct from the raw smoke-test script; this one integrates with Section 3's message loop rather than being a standalone debug tool)
6. `tools/schema.py` — Ollama tool schemas for all 50 tools, organized by the same five phase-categories, `layer_id` marked optional with fallback behavior documented in each relevant description
7. `orchestrator.py` — the main loop described in Section 3, using `socket_client.py` to talk to the GIMP plugin
8. `cli.py` — simple chat loop wrapping the orchestrator
9. A short README covering: how the fork differs from upstream maorcc/gimp-mcp, the confirmed Windows plugin install path, how to start Ollama, how to run the CLI, the full socket protocol spec (including the error response shape), and known limitations

Build and validate in order — don't extend the fork with new tools until its unmodified socket round-trip is proven and its threading model is confirmed safe, don't move to Phase 2 tools until Phase 1's are validated via the raw smoke-test script, don't move to the orchestrator until all 5 phases pass individual testing, and don't move to the CLI until multi-step tool chaining works with at least a couple of tools from different phases in the same chain (e.g. crop then blur then export).