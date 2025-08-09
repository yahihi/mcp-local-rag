#!/bin/bash
set -euo pipefail

# ログ設定（恒久保存）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/setup-$(date +%F-%H%M%S).log"
echo "📒 ログ: $LOG_FILE"
exec > >(tee -a "$LOG_FILE") 2>&1

# MCP Local RAG 初回セットアップスクリプト
# 
# Usage:
#   ./setup.sh                    # config.jsonの設定を使用
#   ./setup.sh /path/to/project   # 特定のディレクトリをインデックス
#   ./setup.sh /path1 /path2      # 複数のディレクトリをインデックス

echo "🚀 MCP Local RAG セットアップを開始します..."
echo ""

# 引数を保存（相対パスを絶対パスに変換）
echo "== STEP: 引数の正規化 =="
ORIGINAL_ARGS=()
for arg in "$@"; do
    if [[ -d "$arg" ]]; then
        # ディレクトリが存在する場合は絶対パスに変換
        ORIGINAL_ARGS+=("$(cd "$arg" && pwd)")
    else
        ORIGINAL_ARGS+=("$arg")
    fi
done

# スクリプトのディレクトリに移動
cd "$(dirname "$0")"

# 依存関係の確認
echo "== STEP: 依存関係の確認 =="
echo "📦 依存関係を確認中..."
if ! uv pip list | grep -q "chromadb" > /dev/null 2>&1; then
    echo "⚠️  依存関係がインストールされていません"
    echo "実行中: uv pip install -r requirements.txt"
    uv pip install -r requirements.txt
else
    echo "✅ 依存関係はインストール済み"
fi

# 埋め込みモデルを事前ダウンロード
echo ""
echo "== STEP: 埋め込みモデルの事前ダウンロード =="
echo "🤖 埋め込みモデルを準備中..."
uv run python -c "
import logging
logging.basicConfig(level=logging.WARNING)  # ログを抑制
print('  all-MiniLM-L6-v2 モデルをダウンロード中...')
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')
print('  ✅ モデルのダウンロード完了！')
" 2>/dev/null || echo "  ⚠️  モデルのダウンロードをスキップ（既存のキャッシュを使用）"

# 初回インデックス作成（保存した絶対パスを渡す）
echo ""
echo "== STEP: 初回インデックス作成 =="
echo "🔍 初回インデックスを作成中..."

# 対象ディレクトリの決定（引数がなければ config.json を参照）
TARGET_DIRS=("${ORIGINAL_ARGS[@]}")
if [ ${#TARGET_DIRS[@]} -eq 0 ]; then
    echo "📁 config.json から対象ディレクトリを取得します..."
    mapfile -t TARGET_DIRS < <(python3 - <<'PY'
import json, os
cfg = json.load(open('config.json'))
dirs = cfg.get('watch_directories') or cfg.get('auto_index', {}).get('watch_directories', [])
for d in dirs:
    if isinstance(d, str):
        print(os.path.abspath(d))
PY
)
fi

# 対象ファイル件数の見積もり（fd/find + config 準拠）
if [ ${#TARGET_DIRS[@]} -gt 0 ]; then
    echo "== STEP: 対象ファイルの見積り =="
    TOTAL=0
    for D in "${TARGET_DIRS[@]}"; do
        if [ -d "$D" ]; then
            LINE=$(bash "$SCRIPT_DIR/scripts/count_candidates.sh" "$D" || true)
            echo "$LINE"
            CNT=$(echo "$LINE" | sed -nE 's/.*: ([0-9]+) files.*/\1/p' | tr -d ' ')
            if [[ "$CNT" =~ ^[0-9]+$ ]]; then
                TOTAL=$((TOTAL + CNT))
            fi
        else
            echo "[skip] $D はディレクトリではありません"
        fi
    done
    echo "📊 合計: ${TOTAL} files"
    read -r -p "この内容でインデックスを進めますか? [y/N]: " ANSWER
    ANS_LC=$(printf '%s' "$ANSWER" | tr '[:upper:]' '[:lower:]')
    case "$ANS_LC" in
        y|yes)
            echo "▶ インデックス作成を続行します"
            ;;
        *)
            echo "⏹ 処理を中止しました"
            exit 0
            ;;
    esac
else
    echo "⚠️  config.json に watch_directories が設定されていません（または引数がありません）"
    echo "    必要に応じて ./setup.sh /path/to/project を再実行してください"
fi

uv run --no-project python scripts/setup_index.py "${ORIGINAL_ARGS[@]}"

echo ""
echo "セットアップ完了！"
echo ""
echo "次のコマンドでMCPサーバーを登録してください:"
echo "  claude mcp add local-rag $(pwd)/run.sh"
echo ""
echo "または環境変数でディレクトリを指定:"
echo "  claude mcp add local-rag $(pwd)/run.sh \\"
echo "    -e MCP_WATCH_DIR_1=\"\$(pwd)\""
