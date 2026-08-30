#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GIMP Agent Orchestration Layer (Deliverable 7)
Coordinates Ollama LLM tool calling with the local GIMP Socket Server.
"""

import os
import sys
import json
import time

from tools.socket_client import GimpSocketClient
from tools.schema import get_all_tools, get_category_tools, ROUTER_TOOL
from llm_providers import LLMProvider, OllamaProvider

MAX_TURNS_PER_REQUEST = 10
# Keep system prompt + this many messages max to avoid context overflow.
MAX_HISTORY_MESSAGES = 30
# Anchor log path to script directory regardless of CWD.
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gimp_agent_session.jsonl")

SYSTEM_PROMPT = """You are an expert AI Image Editor controlling GIMP 3.2 through a library of 50 precise atomic tools organized in 5 categories.

## Tool Categories
- **Canvas & File (Phase 1):** load_image, export_image, duplicate_image, close_image, get_image_info, resize_image, scale_image, crop_image, rotate_image, flip_image
- **Selections & Color (Phase 2):** select_rectangle, select_ellipse, select_by_color, select_all, select_none, invert_selection, adjust_brightness_contrast, adjust_hue_saturation, adjust_levels, desaturate
- **Filters & Effects (Phase 3):** adjust_curves, adjust_color_balance, invert_colors, apply_gaussian_blur, apply_motion_blur, apply_sharpen, apply_pixelize, apply_emboss, apply_noise, apply_edge_detect
- **Layer Management (Phase 4):** add_layer, delete_layer, duplicate_layer, merge_down, flatten_image, set_layer_opacity, set_layer_blend_mode, rename_layer
- **Drawing & Transforms (Phase 5):** add_text_layer, draw_rectangle, draw_ellipse, draw_line, fill_selection, move_layer, scale_layer, rotate_layer, reorder_layer, feather_selection, set_foreground_color, get_layer_info

## CRITICAL: Image vs Layer vs Selection Disambiguation
These are the most common mistake patterns at this tool count — read carefully:
- `scale_image` rescales the ENTIRE canvas + all layers together. `scale_layer` resizes ONE specific layer, canvas unchanged.
- `rotate_image` rotates the ENTIRE image. `rotate_layer` rotates ONE layer only, others stay in place.
- `crop_image` permanently trims the canvas boundary. `select_rectangle` marks a region for follow-up editing (fill, blur, etc.) — it does NOT change the canvas.
- `resize_image` changes canvas size (may add empty space). `scale_image` changes canvas size AND scales content proportionally.
- `select_*` tools CHOOSE a region. `draw_*` tools PAINT pixels. Never substitute one for the other.

## Workflow Rules
1. Start every new task with `get_image_info` (image already open) or `load_image` (given a path). Extract `image_id` and `active_layer_id` from the result and use them in all subsequent calls.
2. For single-layer images you do NOT need to pass `layer_id` — all tools default to the active layer automatically.
3. After each tool call, check `"status"` in the result. If `"error"`, read `"message"` and `"image_state"`, adjust your arguments, and retry. Do not give up after one failure.
4. For region-specific filters, chain selection tools: `select_rectangle` -> `apply_gaussian_blur` -> `select_none`.
5. Use `set_foreground_color` before any `draw_*` or `fill_selection` call when you need a specific color.
6. When all edits are complete, call `export_image` to save, then summarize all changes made clearly.
7. You do not have all 50 tools loaded at once. If you need a tool that is not in your current list, you MUST first call the `request_tool_category` tool to load the correct category.
"""


def log_event(event_type, data):
    """Appends an event to the local session log."""
    entry = {
        "timestamp": time.time(),
        "type": event_type,
        "data": data
    }
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


class GimpAgentOrchestrator:
    def __init__(self, llm_provider: LLMProvider = None, gimp_host="127.0.0.1", gimp_port=9877, use_category_routing=True):
        self.llm_provider = llm_provider or OllamaProvider()
        self.gimp_client = GimpSocketClient(host=gimp_host, port=gimp_port)
        self.use_category_routing = use_category_routing
        self.reset_session()

    def reset_session(self):
        """Resets conversation history and tool configurations to clean initial state."""
        self.messages = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        if self.use_category_routing:
            # Starts with Core Tools (get_image_info, load_image, export_image) + Router Tool
            self.tools = get_category_tools([], accumulate=False)
        else:
            self.tools = get_all_tools()

    def check_environment(self):
        """Verifies connectivity to both GIMP and the configured LLM provider."""
        status = {"gimp": False, "llm": False, "details": {}}

        # Check GIMP
        gimp_ping = self.gimp_client.ping()
        if gimp_ping.get("status") == "success":
            status["gimp"] = True
            status["details"]["gimp"] = "Connected"
        else:
            status["details"]["gimp"] = gimp_ping.get("message")

        # Check LLM
        ok, msg = self.llm_provider.check_connection()
        status["llm"] = ok
        status["details"]["llm"] = msg

        return status

    def process_user_turn(self, user_input, stream_callback=None):
        """
        Executes the agentic loop for a user input turn:
        User Message -> LLM -> Tool Call(s) -> GIMP Execution -> Feedback -> LLM Loop -> Final Output.
        """
        self.messages.append({"role": "user", "content": user_input})
        log_event("user_input", {"content": user_input})

        turn_count = 0
        while turn_count < MAX_TURNS_PER_REQUEST:
            turn_count += 1
            if stream_callback:
                stream_callback(f"Thinking (step {turn_count})...")

            try:
                msg = self.llm_provider.chat(self.messages, self.tools)
            except Exception as e:
                err_msg = f"Error calling LLM ({self.llm_provider.get_name()}): {e}"
                log_event("llm_error", {"error": str(e)})
                return f"[Agent Error] {err_msg}"

            self.messages.append(msg)
            log_event("assistant_message", msg)

            tool_calls = msg.get("tool_calls", [])
            if not tool_calls:
                # LLM finished and returned a conversational response
                return msg.get("content", "Done.")

            # Process all tool calls returned in this turn
            for tc in tool_calls:
                fn = tc.get("function", {})
                tool_name = fn.get("name", "")
                arguments = fn.get("arguments", {})
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except Exception:
                        arguments = {}

                if stream_callback:
                    stream_callback(f"[tool] {tool_name}({arguments})")

                if tool_name == "request_tool_category" and self.use_category_routing:
                    cat = arguments.get("category_name")
                    extra = arguments.get("additional_categories", [])
                    requested = [cat] if cat else []
                    if isinstance(extra, list):
                        requested.extend(extra)
                    
                    self.tools = get_category_tools(requested, current_tools=self.tools, accumulate=True)
                    gimp_result = {
                        "status": "success", 
                        "message": f"Loaded category tools for: {', '.join(requested)}. Total active tools in context: {len(self.tools)}."
                    }
                    log_event("tool_execution", {
                        "tool": tool_name,
                        "arguments": arguments,
                        "result": gimp_result
                    })
                else:
                    # Execute in GIMP
                    gimp_result = self.gimp_client.send_command(tool_name, arguments)
                    log_event("tool_execution", {
                        "tool": tool_name,
                        "arguments": arguments,
                        "result": gimp_result
                    })

                # Append tool result to conversation history
                self.messages.append({
                    "role": "tool",
                    "content": json.dumps(gimp_result)
                })

            # Trim history after each round-trip to prevent context overflow.
            # Keep the system prompt (index 0) + the most recent MAX_HISTORY_MESSAGES.
            if len(self.messages) > MAX_HISTORY_MESSAGES + 1:
                self.messages = [self.messages[0]] + self.messages[-(MAX_HISTORY_MESSAGES):]

        return "Reached maximum tool execution turns (10). Please review the current image state."
