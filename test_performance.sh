#!/bin/bash
set -euo pipefail

echo "🔬 パフォーマンステスト開始"
echo "================================"

# テスト用の小さいディレクトリで実行
TEST_DIR="${1:-./src}"

echo "対象ディレクトリ: $TEST_DIR"
echo ""

# スクリプトのディレクトリに移動
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# デバッグモードで実行
echo "📊 DEBUG モードで実行中..."
LOGLEVEL=DEBUG uv run python scripts/setup_index.py "$TEST_DIR" 2>&1 | tee performance_debug.log

echo ""
echo "ログファイル: performance_debug.log"
echo ""

# タイミング情報を抽出
echo "⏱️  タイミング分析:"
echo "================================"

echo ""
echo "ファイル処理時間:"
grep -E "Indexed .* in [0-9]+\.[0-9]+ms" performance_debug.log | tail -20

echo ""
echo "遅いファイル (1秒以上):"
grep "Slow file:" performance_debug.log || echo "なし"

echo ""
echo "埋め込み生成時間:"
grep -E "Encoded [0-9]+ texts in" performance_debug.log | tail -10

echo ""
echo "データベース書き込み時間:"
grep -E "Added [0-9]+ documents to collection in" performance_debug.log | tail -10

echo ""
echo "遅いDB書き込み (500ms以上):"
grep "Slow DB write:" performance_debug.log || echo "なし"

echo ""
echo "処理速度:"
grep -E "files/sec" performance_debug.log | tail -5

echo ""
echo "================================"
echo "✅ テスト完了"