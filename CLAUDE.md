# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

MCP Local RAG - 高速なローカルファイルRAGシステム。Claude CodeのMCPサーバーとして動作し、コードベースの
セマンティック検索を提供。

## 主要コマンド

### 環境セットアップ
```bash
# 依存関係インストール
uv pip install -r requirements.txt

# 初回セットアップ（モデルダウンロード＋インデックス作成）
./setup.sh /path/to/project

# 複数プロジェクトの場合
./setup.sh /path/to/project1 /path/to/project2
```

### サーバー管理
```bash
# サーバー起動
./run.sh

# 静音モードで起動
./run_quiet.sh

# サーバー停止
./stop.sh
# または
pkill -f "python.*server.py"
```

### テスト実行
```bash
# MCPツールのテスト
uv run python tests/test_mcp_tools.py

# 検索機能のテスト
uv run python tests/test_search.py

# 直接検索のテスト
uv run python tests/test_direct_search.py
```

### デバッグ・動作確認
```bash
# ChromaDBの状態確認
uv run python scripts/debug_chroma.py

# 手動インデックス作成
uv run python scripts/setup_index.py /path/to/project

# インデックス作成例
uv run python examples/index_directory.py

# 検索実行例
uv run python examples/search_codebase.py
```

## アーキテクチャ

### コアコンポーネント
- **server.py**: MCPサーバーのメインエントリポイント
  - 定期的な再インデックス（30秒間隔）
  - fd/findによる変更検出
  - プロジェクト別コレクション管理

- **src/indexer.py**: ファイルインデックス作成
  - チャンク分割（1000文字、200文字オーバーラップ）
  - ハッシュベースの変更検出
  - 100種類以上のファイル拡張子対応

- **src/vectordb.py**: ChromaDBラッパー
  - ベクトル検索
  - コレクション管理
  - メタデータフィルタリング

- **src/search.py**: 検索エンジン
  - セマンティック検索
  - 類似ファイル検索
  - コンテキスト抽出

- **src/embeddings.py**: 埋め込み生成
  - all-MiniLM-L6-v2モデル（軽量・高速）
  - モデルキャッシュ機能

### データ構造
```
data/index/
├── chroma/               # ChromaDBベクトルデータベース
└── file_metadata.json    # ファイルメタデータ（ハッシュ、更新日時）
```

### 環境変数
- `MCP_WATCH_DIR_1`〜`MCP_WATCH_DIR_19`: 監視対象ディレクトリ

### 設定ファイル (config.json)
- `watch_directories`: 監視対象ディレクトリリスト
- `reindex_interval_seconds`: 再インデックス間隔（デフォルト30秒）
- `chunk_size`: チャンクサイズ（デフォルト1000）
- `chunk_overlap`: オーバーラップサイズ（デフォルト200）
- `exclude_dirs`: 除外ディレクトリ

## MCPツール

- `index_directory`: ディレクトリをインデックス化
- `search_codebase`: セマンティック検索
- `get_file_context`: 特定行周辺のコンテキスト取得
- `find_similar`: 類似ファイル検索
- `watch_directory`: 監視対象追加
- `get_index_status`: インデックス状態確認

## 開発時の注意点

- fdコマンドがある場合は優先使用（.gitignore考慮）
- Windowsではfd/findが必要（WSL推奨）
- 埋め込みモデルは初回ダウンロード時のみ時間がかかる
- ChromaDBのpersist()は非推奨（自動永続化）