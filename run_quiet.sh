#!/bin/bash

# MCP Local RAG Server起動スクリプト（静かに起動）

# スクリプトのディレクトリに移動
cd "$(dirname "$0")"

# ログを抑制して起動
export PYTHONWARNINGS="ignore"
exec uv run --no-project python -u server.py 2>/dev/null