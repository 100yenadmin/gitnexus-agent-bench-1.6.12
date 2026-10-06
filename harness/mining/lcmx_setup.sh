#!/usr/bin/env bash
# lcm-x bench setup: run from the repo root. Mirrors .github/workflows/ci.yml (pytest+numpy, hermes-agent ABC stub in gitignored agent/).
set -euo pipefail
uv venv -q .venv --python 3.12
uv pip install -q --python .venv/bin/python pytest pytest-xdist numpy
mkdir -p agent
: > agent/__init__.py
cat > agent/context_engine.py <<'STUB'
"""Minimal stub of hermes-agent ContextEngine ABC for CI."""
class ContextEngine:
    """Base class stub — just enough for LCMEngine to import."""
    def __init__(self, **kwargs):
        self.compression_count = 0
        self.last_prompt_tokens = 0
    def compress(self, messages, current_tokens=None, **kwargs):
        raise NotImplementedError
    def on_session_start(self, session_id, **kwargs):
        pass
    def on_session_end(self, **kwargs):
        pass
    def on_session_reset(self):
        self.compression_count = 0
        self.last_prompt_tokens = 0
    def get_tool_schemas(self):
        return []
    def handle_tool_call(self, name, args, **kwargs):
        raise NotImplementedError
    def get_status(self):
        return {}
STUB
