#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM Provider Abstractions
Provides a standard interface for Ollama, OpenAI, and Gemini.
"""

import os
import json
import urllib.request
import urllib.error

class LLMProvider:
    def check_connection(self):
        """Returns (bool_status, string_message)"""
        raise NotImplementedError

    def chat(self, messages, tools):
        """
        Sends messages and tools to the LLM.
        Returns a response message dict matching OpenAI format:
        {
            "role": "assistant",
            "content": "...",
            "tool_calls": [ ... ]
        }
        """
        raise NotImplementedError

    def get_name(self):
        return "Unknown Provider"


class OllamaProvider(LLMProvider):
    def __init__(self, model="qwen2.5:3b", url="http://127.0.0.1:11434/api/chat"):
        self.model = model
        self.url = url

    def get_name(self):
        return f"Ollama ({self.model})"

    def check_connection(self):
        try:
            # Simple check to tags endpoint
            base = self.url.replace("/api/chat", "/api/tags")
            req = urllib.request.Request(base)
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    return True, "Connected"
                return False, f"HTTP {resp.status}"
        except Exception as e:
            return False, f"Unreachable: {str(e)}"

    def chat(self, messages, tools):
        payload = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "stream": False
        }
        req = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("message", {})


class OpenAIProvider(LLMProvider):
    def __init__(self, model="gpt-4o", api_key=None):
        self.model = model
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.url = "https://api.openai.com/v1/chat/completions"

    def get_name(self):
        return f"OpenAI ({self.model})"

    def check_connection(self):
        if not self.api_key:
            return False, "OPENAI_API_KEY environment variable not set."
        return True, "Key present (unverified)"

    def chat(self, messages, tools):
        if not self.api_key:
            raise ValueError("OpenAI API key missing.")
            
        payload = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto"
        }
        req = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            raise RuntimeError(f"OpenAI API Error {e.code}: {err_body}")


class GeminiProvider(LLMProvider):
    def __init__(self, model="gemini-2.5-flash", api_key=None):
        self.model = model
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        # Use Gemini's OpenAI compatibility endpoint so tool schemas map exactly
        self.url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"

    def get_name(self):
        return f"Google Gemini ({self.model})"

    def check_connection(self):
        if not self.api_key:
            return False, "GEMINI_API_KEY environment variable not set."
        return True, "Key present (unverified)"

    def chat(self, messages, tools):
        if not self.api_key:
            raise ValueError("Gemini API key missing.")
            
        payload = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto"
        }
        req = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            raise RuntimeError(f"Gemini API Error {e.code}: {err_body}")
