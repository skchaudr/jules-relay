#!/usr/bin/env bash
set -euo pipefail
REPO="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO"

echo "=== setup: jules-relay ==="

# 1. Python
python3 --version 2>&1 || { echo "✗ python3 not found"; exit 1; }
echo "✓ python3 $(python3 --version 2>&1 | awk '{print $2}')"

# 2. Install deps
pip install -q -r requirements.txt 2>/dev/null && echo "✓ pip deps installed" || echo "⚠ pip install failed"

# 3. Verify imports
python3 -c "from relay import app; print('relay module OK')" 2>/dev/null && echo "✓ relay module imports" || echo "⚠ relay import failed"

# 4. Run tests
RELAY_TOKEN=test pytest -q test_relay.py --tb=short 2>/dev/null && echo "✓ tests pass" || echo "⚠ tests failed"

# 5. Snapshot
echo "--- snapshot ---"
echo "  branch:  $(git branch --show-current 2>/dev/null || echo 'not a git repo')"
echo "  python:  $(python3 --version 2>&1)"
echo "  setup:   $(date -u +%Y-%m-%dT%H:%M:%SZ)"
