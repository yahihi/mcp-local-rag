#!/bin/bash

# MCP Local RAG 初回セットアップスクリプト
# 
# Usage:
#   ./setup.sh                    # config.jsonの設定を使用
#   ./setup.sh /path/to/project   # 特定のディレクトリをインデックス
#   ./setup.sh /path1 /path2      # 複数のディレクトリをインデックス

echo "🚀 MCP Local RAG セットアップを開始します..."
echo ""

# スクリプトのディレクトリに移動
cd "$(dirname "$0")"

# 依存関係の確認
echo "📦 依存関係を確認中..."
if ! uv pip list | grep -q "chromadb" > /dev/null 2>&1; then
    echo "⚠️  依存関係がインストールされていません"
    echo "実行中: uv pip install -r requirements.txt"
    uv pip install -r requirements.txt
fi

# 埋め込みモデルを事前ダウンロード
echo ""
echo "🤖 埋め込みモデルを準備中..."
uv run python -c "
import logging
logging.basicConfig(level=logging.WARNING)  # ログを抑制
print('  all-MiniLM-L6-v2 モデルをダウンロード中...')
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')
print('  ✅ モデルのダウンロード完了！')
" 2>/dev/null || echo "  ⚠️  モデルのダウンロードをスキップ（既存のキャッシュを使用）"

# 初回インデックス作成（引数をそのまま渡す）
echo ""
echo "🔍 初回インデックスを作成中..."
uv run --no-project python scripts/setup_index.py "$@"

echo ""
echo "セットアップ完了！"
echo ""
echo "次のコマンドでMCPサーバーを登録してください:"
echo "  claude mcp add local-rag $(pwd)/run.sh"
echo ""
echo "または環境変数でディレクトリを指定:"
echo "  claude mcp add local-rag $(pwd)/run.sh \\"
echo "    -e MCP_WATCH_DIR_1=\"\$(pwd)\""