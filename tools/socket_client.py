#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GIMP Socket Client Library (Deliverable 5)
Provides a clean Python interface to communicate with the in-GIMP AI Agent Socket Server.
"""

import socket
import json
import time

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9877
DEFAULT_TIMEOUT = 30.0


class GimpSocketClient:
    """Client interface for communicating with the GIMP Agent socket server."""

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT, timeout=DEFAULT_TIMEOUT):
        self.host = host
        self.port = port
        self.timeout = timeout

    def send_command(self, cmd_type, params=None):
        """
        Sends a single JSON command to GIMP and awaits the structured response.
        
        Args:
            cmd_type (str): The tool/command name (e.g. 'load_image', 'crop_image', 'ping')
            params (dict, optional): Keyword arguments for the tool.
            
        Returns:
            dict: The JSON response containing 'status', 'data' / 'error_type' + 'message', and 'image_state'.
        """
        if params is None:
            params = {}

        payload = json.dumps({
            "type": cmd_type,
            "params": params
        }).encode("utf-8")

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)

        try:
            sock.connect((self.host, self.port))
            sock.sendall(payload)

            chunks = []
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                chunks.append(chunk)

            raw_resp = b"".join(chunks).decode("utf-8")
            if not raw_resp.strip():
                return {
                    "status": "error",
                    "error_type": "EmptyResponseError",
                    "message": "GIMP socket server returned empty response",
                    "image_state": {}
                }

            return json.loads(raw_resp)

        except ConnectionRefusedError:
            return {
                "status": "error",
                "error_type": "ConnectionRefusedError",
                "message": f"Cannot connect to GIMP Agent Server at {self.host}:{self.port}. Ensure GIMP 3.2.4 is running and 'Tools > AI Agent > Start AI Agent Server' is active.",
                "image_state": {}
            }
        except socket.timeout:
            return {
                "status": "error",
                "error_type": "TimeoutError",
                "message": f"Socket request '{cmd_type}' timed out after {self.timeout}s",
                "image_state": {}
            }
        except Exception as e:
            return {
                "status": "error",
                "error_type": type(e).__name__,
                "message": str(e),
                "image_state": {}
            }
        finally:
            try:
                sock.close()
            except Exception:
                pass

    def ping(self):
        """Check if server is responding."""
        return self.send_command("ping")

    def get_info(self):
        """Get GIMP system information."""
        return self.send_command("get_gimp_info")
