#!/bin/bash

# MCP Local RAG Server起動スクリプト

# スクリプトのディレクトリに移動
cd "$(dirname "$0")"

# サーバー起動（--no-projectで直接実行）
exec uv run --no-project python server.py