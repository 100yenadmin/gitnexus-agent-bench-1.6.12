#!/usr/bin/env bash
# hermes-agent bench setup (Track H): run from the repo root. Builds .venv from the committed uv.lock with the
# dependency groups and extras CI's main test lane installs (.github/workflows/tests.yml: dev+test groups;
# extras all, anthropic, bedrock, mistral, fal, modal, daytona, parallel-web). --no-install-project: the
# checkout itself is never installed (an editable .pth would pin imports to THIS directory after the venv
# is APFS-copied into a bench base/run dir); hermes_pytest.sh puts the repo root on PYTHONPATH instead.
set -euo pipefail
uv sync -q --frozen --no-install-project --group dev --group test \
  --extra all --extra anthropic --extra bedrock --extra mistral --extra fal --extra modal --extra daytona --extra parallel-web
.venv/bin/python -c 'import pytest, sys; print("venv ok", sys.version.split()[0], "pytest", pytest.__version__)'
