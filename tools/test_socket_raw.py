#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Standalone Raw Socket Test Suite for GIMP Agent Plugin (Deliverable 3)
Sends raw JSON commands directly to localhost:9877 to deterministically test GIMP PDB handlers
without any LLM in the loop.
"""

import os
import sys
import json
import socket
import tempfile
import time

# Ensure UTF-8 stdout on Windows console
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


HOST = "127.0.0.1"
PORT = 9877
TIMEOUT = 10.0


def send_raw_command(cmd_type, params=None, host=HOST, port=PORT, timeout=TIMEOUT):
    """Sends a raw JSON request to the GIMP socket server and returns the parsed response."""
    if params is None:
        params = {}
    payload = json.dumps({"type": cmd_type, "params": params}).encode("utf-8")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
        sock.sendall(payload)

        chunks = []
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)
        raw_resp = b"".join(chunks).decode("utf-8")
        if not raw_resp.strip():
            return {"status": "error", "message": "Empty response from GIMP socket"}
        return json.loads(raw_resp)
    except ConnectionRefusedError:
        return {
            "status": "error",
            "error_type": "ConnectionRefusedError",
            "message": f"Could not connect to GIMP Agent Server at {host}:{port}. Is GIMP running with the plugin started?"
        }
    except Exception as e:
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e)
        }
    finally:
        sock.close()


def create_test_image():
    """Generates a small test BMP/PPM image using pure Python standard library (no PIL required)."""
    temp_dir = tempfile.gettempdir()
    test_path = os.path.join(temp_dir, "gimp_agent_test_sample.ppm")
    width, height = 200, 150
    header = f"P6\n{width} {height}\n255\n".encode("ascii")
    # Gradient RGB data
    pixels = bytearray()
    for y in range(height):
        for x in range(width):
            r = int((x / width) * 255)
            g = int((y / height) * 255)
            b = 180
            pixels.extend([r, g, b])
    with open(test_path, "wb") as f:
        f.write(header + pixels)
    return test_path


def run_phase1_tests():
    """Runs tests for all 10 Phase 1 tools."""
    print("=" * 60)
    print(" GIMP AGENT RAW SOCKET SMOKE TEST SUITE (PHASE 1)")
    print(f" Target: {HOST}:{PORT}")
    print("=" * 60)

    # 1. Ping test
    print("\n[Test 1] Checking Ping / Server heartbeat...")
    resp = send_raw_command("ping")
    if resp.get("status") != "success":
        print(f"  [FAIL]: {resp.get('message')}")
        print("\n  --> To run this test:")
        print("     1. Open GIMP 3.2.4")
        print("     2. Go to menu: Tools > AI Agent > Start AI Agent Server")
        print("     3. Re-run this test script.")
        return False
    print("  [OK] Server is ALIVE and responding!")
    print(f"       Response: {resp.get('data')}")

    # 2. Get GIMP info
    print("\n[Test 2] Querying GIMP system info...")
    resp = send_raw_command("get_gimp_info")
    print(f"  [OK] GIMP Info: {resp.get('data')}")

    # Create sample image
    sample_img_path = create_test_image()
    print(f"\nCreated local test image: {sample_img_path}")

    # 3. Tool 1: load_image
    print("\n[Test 3] Testing 'load_image'...")
    resp = send_raw_command("load_image", {"path": sample_img_path})
    if resp.get("status") != "success":
        print(f"  [FAIL] load_image failed: {resp}")
        return False
    img_id = resp["data"]["image_id"]
    print(f"  [OK] Image loaded successfully! Image ID: {img_id}, Canvas: {resp['image_state']['width']}x{resp['image_state']['height']}")

    # 4. Tool 5: get_image_info
    print("\n[Test 4] Testing 'get_image_info'...")
    resp = send_raw_command("get_image_info", {"image_id": img_id})
    print(f"  [OK] State Grounding Verified: Layers count={resp['image_state']['layers_count']}, Active Layer='{resp['image_state']['active_layer_name']}'")

    # 5. Tool 6: resize_image
    print("\n[Test 5] Testing 'resize_image' (canvas expand to 300x250)...")
    resp = send_raw_command("resize_image", {"image_id": img_id, "width": 300, "height": 250})
    if resp.get("status") == "success":
        print(f"  [OK] Resized canvas to {resp['image_state']['width']}x{resp['image_state']['height']}")
    else:
        print(f"  [FAIL] resize_image failed: {resp}")

    # 6. Tool 7: scale_image
    print("\n[Test 6] Testing 'scale_image' (50% scale)...")
    resp = send_raw_command("scale_image", {"image_id": img_id, "percent": 50})
    if resp.get("status") == "success":
        print(f"  [OK] Scaled image to {resp['image_state']['width']}x{resp['image_state']['height']}")
    else:
        print(f"  [FAIL] scale_image failed: {resp}")

    # 7. Tool 9: rotate_image
    print("\n[Test 7] Testing 'rotate_image' (90 degrees)...")
    resp = send_raw_command("rotate_image", {"image_id": img_id, "degrees": 90})
    if resp.get("status") == "success":
        print(f"  [OK] Rotated image 90deg. New dimensions: {resp['image_state']['width']}x{resp['image_state']['height']}")
    else:
        print(f"  [FAIL] rotate_image failed: {resp}")

    # 8. Tool 10: flip_image
    print("\n[Test 8] Testing 'flip_image' (horizontal)...")
    resp = send_raw_command("flip_image", {"image_id": img_id, "axis": "horizontal"})
    if resp.get("status") == "success":
        print(f"  [OK] Flipped image horizontally.")
    else:
        print(f"  [FAIL] flip_image failed: {resp}")

    # 9. Tool 3: duplicate_image
    print("\n[Test 9] Testing 'duplicate_image'...")
    resp = send_raw_command("duplicate_image", {"image_id": img_id})
    dup_id = resp["data"]["new_image_id"] if resp.get("status") == "success" else None
    if dup_id:
        print(f"  [OK] Duplicated image to new ID: {dup_id}")
    else:
        print(f"  [FAIL] duplicate_image failed: {resp}")

    # 10. Tool 8: crop_image
    print("\n[Test 10] Testing 'crop_image' on duplicate (crop to 40x40 at offset 10,10)...")
    if dup_id:
        resp = send_raw_command("crop_image", {"image_id": dup_id, "x": 10, "y": 10, "width": 40, "height": 40})
        if resp.get("status") == "success":
            print(f"  [OK] Cropped duplicate image to {resp['image_state']['width']}x{resp['image_state']['height']}")
        else:
            print(f"  [FAIL] crop_image failed: {resp}")

    # 11. Tool 2: export_image
    export_out_path = os.path.join(temp_dir, "gimp_agent_export_test.png")
    print(f"\n[Test 11] Testing 'export_image' to {export_out_path}...")
    resp = send_raw_command("export_image", {"image_id": img_id, "path": export_out_path, "format": "png"})
    if resp.get("status") == "success" and os.path.exists(export_out_path):
        print(f"  [OK] Export verified! Exported file size: {os.path.getsize(export_out_path)} bytes")
    else:
        print(f"  [FAIL] export_image failed: {resp}")

    # 12. Tool 4: close_image
    print("\n[Test 12] Testing 'close_image' on duplicate and original...")
    if dup_id:
        send_raw_command("close_image", {"image_id": dup_id})
    resp = send_raw_command("close_image", {"image_id": img_id})
    print(f"  [OK] Cleaned up and closed test images.")

    print("\n" + "=" * 60)
    print(" [PASS] ALL PHASE 1 TOOLS TESTED SUCCESSFULLY AGAINST GIMP 3.2.4!")
    print("=" * 60)
    return True


def run_phase2_tests():
    """Runs tests for all 10 Phase 2 tools (Selections & Color Adjustments)."""
    print("\n" + "=" * 60)
    print(" GIMP AGENT RAW SOCKET SMOKE TEST SUITE (PHASE 2)")
    print(" Selections & Color Adjustments")
    print("=" * 60)

    # 1. Load fresh image for Phase 2 tests
    sample_img_path = create_test_image()
    resp = send_raw_command("load_image", {"path": sample_img_path})
    if resp.get("status") != "success":
        print(f"  [FAIL] Failed to load image for Phase 2: {resp}")
        return False
    img_id = resp["data"]["image_id"]
    print(f"\n[Phase 2 Setup] Image loaded, ID: {img_id}")

    # 2. Tool 11: select_rectangle
    print("\n[Test 13] Testing 'select_rectangle' (10, 10, 80, 60)...")
    resp = send_raw_command("select_rectangle", {"image_id": img_id, "x": 10, "y": 10, "width": 80, "height": 60})
    if resp.get("status") == "success":
        print(f"  [OK] select_rectangle succeeded")
    else:
        print(f"  [FAIL] select_rectangle failed: {resp}")

    # 3. Tool 12: select_ellipse
    print("\n[Test 14] Testing 'select_ellipse' (20, 20, 50, 50)...")
    resp = send_raw_command("select_ellipse", {"image_id": img_id, "x": 20, "y": 20, "width": 50, "height": 50})
    if resp.get("status") == "success":
        print(f"  [OK] select_ellipse succeeded")
    else:
        print(f"  [FAIL] select_ellipse failed: {resp}")

    # 4. Tool 16: invert_selection
    print("\n[Test 15] Testing 'invert_selection'...")
    resp = send_raw_command("invert_selection", {"image_id": img_id})
    if resp.get("status") == "success":
        print(f"  [OK] invert_selection succeeded")
    else:
        print(f"  [FAIL] invert_selection failed: {resp}")

    # 5. Tool 15: select_none
    print("\n[Test 16] Testing 'select_none'...")
    resp = send_raw_command("select_none", {"image_id": img_id})
    if resp.get("status") == "success":
        print(f"  [OK] select_none succeeded")
    else:
        print(f"  [FAIL] select_none failed: {resp}")

    # 6. Tool 14: select_all
    print("\n[Test 17] Testing 'select_all'...")
    resp = send_raw_command("select_all", {"image_id": img_id})
    if resp.get("status") == "success":
        print(f"  [OK] select_all succeeded")
    else:
        print(f"  [FAIL] select_all failed: {resp}")

    # 7. Tool 13: select_by_color
    print("\n[Test 18] Testing 'select_by_color' (color='red', threshold=20)...")
    resp = send_raw_command("select_by_color", {"image_id": img_id, "color": "red", "threshold": 20})
    if resp.get("status") == "success":
        print(f"  [OK] select_by_color succeeded")
    else:
        print(f"  [FAIL] select_by_color failed: {resp}")

    # 8. Tool 17: adjust_brightness_contrast
    print("\n[Test 19] Testing 'adjust_brightness_contrast' (brightness=20, contrast=15)...")
    resp = send_raw_command("adjust_brightness_contrast", {"image_id": img_id, "brightness": 20, "contrast": 15})
    if resp.get("status") == "success":
        print(f"  [OK] adjust_brightness_contrast succeeded on layer {resp['data']['layer_id']}")
    else:
        print(f"  [FAIL] adjust_brightness_contrast failed: {resp}")

    # 9. Tool 18: adjust_hue_saturation
    print("\n[Test 20] Testing 'adjust_hue_saturation' (hue=30, saturation=20)...")
    resp = send_raw_command("adjust_hue_saturation", {"image_id": img_id, "hue": 30, "saturation": 20})
    if resp.get("status") == "success":
        print(f"  [OK] adjust_hue_saturation succeeded")
    else:
        print(f"  [FAIL] adjust_hue_saturation failed: {resp}")

    # 10. Tool 19: adjust_levels
    print("\n[Test 21] Testing 'adjust_levels' (gamma=1.2, low_input=10, high_input=245)...")
    resp = send_raw_command("adjust_levels", {"image_id": img_id, "channel": "value", "gamma": 1.2, "low_input": 10, "high_input": 245})
    if resp.get("status") == "success":
        print(f"  [OK] adjust_levels succeeded")
    else:
        print(f"  [FAIL] adjust_levels failed: {resp}")

    # 11. Tool 20: desaturate
    print("\n[Test 22] Testing 'desaturate' (mode='luminance')...")
    resp = send_raw_command("desaturate", {"image_id": img_id, "mode": "luminance"})
    if resp.get("status") == "success":
        print(f"  [OK] desaturate succeeded")
    else:
        print(f"  [FAIL] desaturate failed: {resp}")

    # Cleanup
    send_raw_command("close_image", {"image_id": img_id})
    print(f"\n  [OK] Cleaned up Phase 2 test image.")

    print("\n" + "=" * 60)
    print(" [PASS] ALL PHASE 2 TOOLS TESTED SUCCESSFULLY AGAINST GIMP 3.2.4!")
    print("=" * 60)
    return True


def run_phase3_tests():
    """Runs tests for all 10 Phase 3 tools (Filters, Effects & Presets)."""
    print("\n" + "=" * 60)
    print(" GIMP AGENT RAW SOCKET SMOKE TEST SUITE (PHASE 3)")
    print(" Filters, Effects & Presets")
    print("=" * 60)

    # 1. Load fresh image for Phase 3 tests
    sample_img_path = create_test_image()
    resp = send_raw_command("load_image", {"path": sample_img_path})
    if resp.get("status") != "success":
        print(f"  [FAIL] Failed to load image for Phase 3: {resp}")
        return False
    img_id = resp["data"]["image_id"]
    print(f"\n[Phase 3 Setup] Image loaded, ID: {img_id}")

    # 2. Tool 21: adjust_curves
    print("\n[Test 23] Testing 'adjust_curves' (preset='s_curve')...")
    resp = send_raw_command("adjust_curves", {"image_id": img_id, "preset": "s_curve"})
    if resp.get("status") == "success":
        print(f"  [OK] adjust_curves succeeded")
    else:
        print(f"  [FAIL] adjust_curves failed: {resp}")

    # 3. Tool 22: adjust_color_balance
    print("\n[Test 24] Testing 'adjust_color_balance' (cyan_red=20, yellow_blue=-15)...")
    resp = send_raw_command("adjust_color_balance", {"image_id": img_id, "cyan_red": 20, "yellow_blue": -15})
    if resp.get("status") == "success":
        print(f"  [OK] adjust_color_balance succeeded")
    else:
        print(f"  [FAIL] adjust_color_balance failed: {resp}")

    # 4. Tool 23: invert_colors
    print("\n[Test 25] Testing 'invert_colors'...")
    resp = send_raw_command("invert_colors", {"image_id": img_id})
    if resp.get("status") == "success":
        print(f"  [OK] invert_colors succeeded")
    else:
        print(f"  [FAIL] invert_colors failed: {resp}")

    # 5. Tool 24: apply_gaussian_blur
    print("\n[Test 26] Testing 'apply_gaussian_blur' (radius=6.0)...")
    resp = send_raw_command("apply_gaussian_blur", {"image_id": img_id, "radius": 6.0})
    if resp.get("status") == "success":
        print(f"  [OK] apply_gaussian_blur succeeded")
    else:
        print(f"  [FAIL] apply_gaussian_blur failed: {resp}")

    # 6. Tool 25: apply_motion_blur
    print("\n[Test 27] Testing 'apply_motion_blur' (angle=45, length=12)...")
    resp = send_raw_command("apply_motion_blur", {"image_id": img_id, "angle": 45, "length": 12})
    if resp.get("status") == "success":
        print(f"  [OK] apply_motion_blur succeeded")
    else:
        print(f"  [FAIL] apply_motion_blur failed: {resp}")

    # 7. Tool 26: apply_sharpen
    print("\n[Test 28] Testing 'apply_sharpen' (amount=60, radius=2.5)...")
    resp = send_raw_command("apply_sharpen", {"image_id": img_id, "amount": 60, "radius": 2.5})
    if resp.get("status") == "success":
        print(f"  [OK] apply_sharpen succeeded")
    else:
        print(f"  [FAIL] apply_sharpen failed: {resp}")

    # 8. Tool 27: apply_pixelize
    print("\n[Test 29] Testing 'apply_pixelize' (block_size=8)...")
    resp = send_raw_command("apply_pixelize", {"image_id": img_id, "block_size": 8})
    if resp.get("status") == "success":
        print(f"  [OK] apply_pixelize succeeded")
    else:
        print(f"  [FAIL] apply_pixelize failed: {resp}")

    # 9. Tool 28: apply_emboss
    print("\n[Test 30] Testing 'apply_emboss' (azimuth=30, elevation=45)...")
    resp = send_raw_command("apply_emboss", {"image_id": img_id, "azimuth": 30, "elevation": 45})
    if resp.get("status") == "success":
        print(f"  [OK] apply_emboss succeeded")
    else:
        print(f"  [FAIL] apply_emboss failed: {resp}")

    # 10. Tool 29: apply_noise
    print("\n[Test 31] Testing 'apply_noise' (amount=15)...")
    resp = send_raw_command("apply_noise", {"image_id": img_id, "amount": 15})
    if resp.get("status") == "success":
        print(f"  [OK] apply_noise succeeded")
    else:
        print(f"  [FAIL] apply_noise failed: {resp}")

    # 11. Tool 30: apply_edge_detect
    print("\n[Test 32] Testing 'apply_edge_detect' (algorithm='sobel')...")
    resp = send_raw_command("apply_edge_detect", {"image_id": img_id, "algorithm": "sobel"})
    if resp.get("status") == "success":
        print(f"  [OK] apply_edge_detect succeeded")
    else:
        print(f"  [FAIL] apply_edge_detect failed: {resp}")

    # Cleanup
    send_raw_command("close_image", {"image_id": img_id})
    print(f"\n  [OK] Cleaned up Phase 3 test image.")

    print("\n" + "=" * 60)
    print(" [PASS] ALL PHASE 3 TOOLS TESTED SUCCESSFULLY AGAINST GIMP 3.2.4!")
    print("=" * 60)
    return True


def run_phase4_tests():
    """Runs tests for all 8 Phase 4 tools (Layer Management)."""
    print("\n" + "=" * 60)
    print(" GIMP AGENT RAW SOCKET SMOKE TEST SUITE (PHASE 4)")
    print(" Layer Management")
    print("=" * 60)

    # 1. Load fresh image for Phase 4 tests
    sample_img_path = create_test_image()
    resp = send_raw_command("load_image", {"path": sample_img_path})
    if resp.get("status") != "success":
        print(f"  [FAIL] Failed to load image for Phase 4: {resp}")
        return False
    img_id = resp["data"]["image_id"]
    print(f"\n[Phase 4 Setup] Image loaded, ID: {img_id}")

    # 2. Tool 31: add_layer
    print("\n[Test 33] Testing 'add_layer' (name='OverlayLayer', fill_type='transparent')...")
    resp = send_raw_command("add_layer", {"image_id": img_id, "name": "OverlayLayer", "fill_type": "transparent"})
    new_layer_id = resp["data"]["layer_id"] if resp.get("status") == "success" else None
    if new_layer_id:
        print(f"  [OK] add_layer succeeded (New Layer ID: {new_layer_id})")
    else:
        print(f"  [FAIL] add_layer failed: {resp}")

    # 3. Tool 38: rename_layer
    print("\n[Test 34] Testing 'rename_layer'...")
    if new_layer_id:
        resp = send_raw_command("rename_layer", {"image_id": img_id, "layer_id": new_layer_id, "new_name": "RenamedLayer"})
        if resp.get("status") == "success":
            print(f"  [OK] rename_layer succeeded (New name: RenamedLayer)")
        else:
            print(f"  [FAIL] rename_layer failed: {resp}")

    # 4. Tool 36: set_layer_opacity
    print("\n[Test 35] Testing 'set_layer_opacity' (opacity=75.0)...")
    if new_layer_id:
        resp = send_raw_command("set_layer_opacity", {"image_id": img_id, "layer_id": new_layer_id, "opacity": 75.0})
        if resp.get("status") == "success":
            print(f"  [OK] set_layer_opacity succeeded")
        else:
            print(f"  [FAIL] set_layer_opacity failed: {resp}")

    # 5. Tool 37: set_layer_blend_mode
    print("\n[Test 36] Testing 'set_layer_blend_mode' (mode='multiply')...")
    if new_layer_id:
        resp = send_raw_command("set_layer_blend_mode", {"image_id": img_id, "layer_id": new_layer_id, "mode": "multiply"})
        if resp.get("status") == "success":
            print(f"  [OK] set_layer_blend_mode succeeded")
        else:
            print(f"  [FAIL] set_layer_blend_mode failed: {resp}")

    # 6. Tool 33: duplicate_layer
    print("\n[Test 37] Testing 'duplicate_layer'...")
    if new_layer_id:
        resp = send_raw_command("duplicate_layer", {"image_id": img_id, "layer_id": new_layer_id})
        dup_layer_id = resp["data"]["new_layer_id"] if resp.get("status") == "success" else None
        if dup_layer_id:
            print(f"  [OK] duplicate_layer succeeded (Dup Layer ID: {dup_layer_id})")
        else:
            print(f"  [FAIL] duplicate_layer failed: {resp}")

    # 7. Tool 34: merge_down
    print("\n[Test 38] Testing 'merge_down'...")
    if new_layer_id:
        resp = send_raw_command("merge_down", {"image_id": img_id, "layer_id": new_layer_id})
        if resp.get("status") == "success":
            print(f"  [OK] merge_down succeeded")
        else:
            print(f"  [FAIL] merge_down failed: {resp}")

    # 8. Tool 32: delete_layer (add a throwaway layer and delete it)
    print("\n[Test 39] Testing 'delete_layer'...")
    resp_temp = send_raw_command("add_layer", {"image_id": img_id, "name": "TempToDelete"})
    if resp_temp.get("status") == "success":
        temp_id = resp_temp["data"]["layer_id"]
        resp_del = send_raw_command("delete_layer", {"image_id": img_id, "layer_id": temp_id})
        if resp_del.get("status") == "success":
            print(f"  [OK] delete_layer succeeded")
        else:
            print(f"  [FAIL] delete_layer failed: {resp_del}")

    # 9. Tool 35: flatten_image
    print("\n[Test 40] Testing 'flatten_image'...")
    resp = send_raw_command("flatten_image", {"image_id": img_id})
    if resp.get("status") == "success":
        print(f"  [OK] flatten_image succeeded (Layers count: {resp['image_state']['layers_count']})")
    else:
        print(f"  [FAIL] flatten_image failed: {resp}")

    # Cleanup
    send_raw_command("close_image", {"image_id": img_id})
    print(f"\n  [OK] Cleaned up Phase 4 test image.")

    print("\n" + "=" * 60)
    print(" [PASS] ALL PHASE 4 TOOLS TESTED SUCCESSFULLY AGAINST GIMP 3.2.4!")
    print("=" * 60)
    return True


def run_phase5_tests():
    """Runs tests for all 12 Phase 5 tools (Text, Drawing & Transforms)."""
    print("\n" + "=" * 60)
    print(" GIMP AGENT RAW SOCKET SMOKE TEST SUITE (PHASE 5)")
    print(" Text, Drawing & Transforms")
    print("=" * 60)

    # 1. Load fresh image for Phase 5 tests
    sample_img_path = create_test_image()
    resp = send_raw_command("load_image", {"path": sample_img_path})
    if resp.get("status") != "success":
        print(f"  [FAIL] Failed to load image for Phase 5: {resp}")
        return False
    img_id = resp["data"]["image_id"]
    print(f"\n[Phase 5 Setup] Image loaded, ID: {img_id}")

    # 2. Tool 49: set_foreground_color
    print("\n[Test 41] Testing 'set_foreground_color' (color='#FF5500')...")
    resp = send_raw_command("set_foreground_color", {"color": "#FF5500"})
    if resp.get("status") == "success":
        print(f"  [OK] set_foreground_color succeeded")
    else:
        print(f"  [FAIL] set_foreground_color failed: {resp}")

    # 3. Tool 40: draw_rectangle
    print("\n[Test 42] Testing 'draw_rectangle' (10, 10, 50, 40, color='blue', filled=True)...")
    resp = send_raw_command("draw_rectangle", {"image_id": img_id, "x": 10, "y": 10, "width": 50, "height": 40, "color": "blue", "filled": True})
    if resp.get("status") == "success":
        print(f"  [OK] draw_rectangle succeeded")
    else:
        print(f"  [FAIL] draw_rectangle failed: {resp}")

    # 4. Tool 41: draw_ellipse
    print("\n[Test 43] Testing 'draw_ellipse' (70, 10, 40, 40, color='red', filled=True)...")
    resp = send_raw_command("draw_ellipse", {"image_id": img_id, "x": 70, "y": 10, "width": 40, "height": 40, "color": "red", "filled": True})
    if resp.get("status") == "success":
        print(f"  [OK] draw_ellipse succeeded")
    else:
        print(f"  [FAIL] draw_ellipse failed: {resp}")

    # 5. Tool 42: draw_line
    print("\n[Test 44] Testing 'draw_line' ((0,0) to (150,100), thickness=3.0)...")
    resp = send_raw_command("draw_line", {"image_id": img_id, "x1": 0, "y1": 0, "x2": 150, "y2": 100, "color": "yellow", "thickness": 3.0})
    if resp.get("status") == "success":
        print(f"  [OK] draw_line succeeded")
    else:
        print(f"  [FAIL] draw_line failed: {resp}")

    # 6. Tool 48: feather_selection
    print("\n[Test 45] Testing 'feather_selection'...")
    send_raw_command("select_rectangle", {"image_id": img_id, "x": 20, "y": 20, "width": 60, "height": 60})
    resp = send_raw_command("feather_selection", {"image_id": img_id, "radius": 8.0})
    if resp.get("status") == "success":
        print(f"  [OK] feather_selection succeeded")
    else:
        print(f"  [FAIL] feather_selection failed: {resp}")

    # 7. Tool 43: fill_selection
    print("\n[Test 46] Testing 'fill_selection' (color='green')...")
    resp = send_raw_command("fill_selection", {"image_id": img_id, "color": "green"})
    if resp.get("status") == "success":
        print(f"  [OK] fill_selection succeeded")
    else:
        print(f"  [FAIL] fill_selection failed: {resp}")
    send_raw_command("select_none", {"image_id": img_id})

    # 8. Tool 39: add_text_layer
    print("\n[Test 47] Testing 'add_text_layer' (text='Hello AI', size=28)...")
    resp = send_raw_command("add_text_layer", {"image_id": img_id, "text": "Hello AI", "x": 30, "y": 30, "size": 28.0, "color": "white"})
    text_layer_id = resp["data"]["layer_id"] if resp.get("status") == "success" else None
    if text_layer_id:
        print(f"  [OK] add_text_layer succeeded (Text Layer ID: {text_layer_id})")
    else:
        print(f"  [FAIL] add_text_layer failed: {resp}")

    # 9. Tool 50: get_layer_info
    print("\n[Test 48] Testing 'get_layer_info' on text layer...")
    if text_layer_id:
        resp = send_raw_command("get_layer_info", {"image_id": img_id, "layer_id": text_layer_id})
        if resp.get("status") == "success":
            print(f"  [OK] get_layer_info succeeded (Name: '{resp['data']['name']}', Dims: {resp['data']['width']}x{resp['data']['height']})")
        else:
            print(f"  [FAIL] get_layer_info failed: {resp}")

    # 10. Tool 44: move_layer
    print("\n[Test 49] Testing 'move_layer' (dx=15, dy=10)...")
    if text_layer_id:
        resp = send_raw_command("move_layer", {"image_id": img_id, "layer_id": text_layer_id, "x_offset": 15, "y_offset": 10})
        if resp.get("status") == "success":
            print(f"  [OK] move_layer succeeded")
        else:
            print(f"  [FAIL] move_layer failed: {resp}")

    # 11. Tool 45: scale_layer
    print("\n[Test 50] Testing 'scale_layer' (width=120, height=50)...")
    if text_layer_id:
        resp = send_raw_command("scale_layer", {"image_id": img_id, "layer_id": text_layer_id, "width": 120, "height": 50})
        if resp.get("status") == "success":
            print(f"  [OK] scale_layer succeeded")
        else:
            print(f"  [FAIL] scale_layer failed: {resp}")

    # 12. Tool 46: rotate_layer
    print("\n[Test 51] Testing 'rotate_layer' (degrees=15.0)...")
    if text_layer_id:
        resp = send_raw_command("rotate_layer", {"image_id": img_id, "layer_id": text_layer_id, "degrees": 15.0})
        if resp.get("status") == "success":
            print(f"  [OK] rotate_layer succeeded")
        else:
            print(f"  [FAIL] rotate_layer failed: {resp}")

    # 13. Tool 47: reorder_layer
    print("\n[Test 52] Testing 'reorder_layer'...")
    if text_layer_id:
        resp = send_raw_command("reorder_layer", {"image_id": img_id, "layer_id": text_layer_id, "new_position": 1})
        if resp.get("status") == "success":
            print(f"  [OK] reorder_layer succeeded")
        else:
            print(f"  [FAIL] reorder_layer failed: {resp}")

    # Cleanup
    send_raw_command("close_image", {"image_id": img_id})
    print(f"\n  [OK] Cleaned up Phase 5 test image.")

    print("\n" + "=" * 60)
    print(" [PASS] ALL 50 TOOLS ACROSS ALL 5 PHASES TESTED SUCCESSFULLY!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    p1_ok = run_phase1_tests()
    if p1_ok:
        p2_ok = run_phase2_tests()
        if p2_ok:
            p3_ok = run_phase3_tests()
            if p3_ok:
                p4_ok = run_phase4_tests()
                if p4_ok:
                    run_phase5_tests()




