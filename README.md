# MCP Local RAG 🚀

高速で効率的なローカルファイルRAG（Retrieval-Augmented Generation）システム。
[Claude Code](https://claude.ai/code)のMCP（Model Context Protocol）サーバーとして動作します。

## ✨ 特徴

### 🚀 高速起動
- 埋め込みモデルのキャッシュ機能
- 初回起動後は約3秒で起動完了
- 軽量なall-MiniLM-L6-v2モデル使用

### 🔄 自動インデックス更新
- 30秒ごとにファイル変更を自動検知
- 新規ファイルの追加、既存ファイルの変更、削除を検出
- fd（推奨）またはfindコマンドを使用
- `.gitignore`を自動的に考慮（fd使用時）

### 🎯 インテリジェントなファイル管理
- 指定ディレクトリを自動監視
- 削除されたファイルを自動検出・クリーンアップ
- 重複エントリを防ぐハッシュベースの変更検出

### 🔍 高度な検索機能
- セマンティック検索で意味的に関連するコードを発見
- 複数クエリーのアグリゲーション検索に対応
- 類似ファイル検索で関連コードを探索
- 特定行周辺のコンテキスト抽出
- 日本語クエリを完全サポート

## 📦 インストール

### 前提条件
- Python 3.10以上
- [uv](https://github.com/astral-sh/uv) (推奨) または pip
- [Claude Code CLI](https://claude.ai/code)
- [fd](https://github.com/sharkdp/fd) (推奨) - `.gitignore`を考慮した高速ファイル検索

### fdのインストール（推奨）
fdをインストールすると、`.gitignore`を自動的に考慮してファイル変更を検出します：

```bash
# macOS
brew install fd

# Ubuntu/Debian
apt install fd-find

# その他のLinux
cargo install fd-find

# Windows (scoop)
scoop install fd
```

※ fdがなくても動作しますが、findコマンドを使用するため`.gitignore`は考慮されません。

### クイックスタート（推奨）

```bash
# 1. リポジトリをクローン
git clone https://github.com/yourusername/mcp-local-rag.git
cd mcp-local-rag

# 2. セットアップ & 初回インデックス作成（重要！）
# 対象プロジェクトをインデックス
./setup.sh ~/projects/my-app

# または複数のプロジェクトを一度にインデックス
./setup.sh ~/projects/app1 ~/projects/app2

# 3. Claude Codeに登録（環境変数でディレクトリを指定）
# 注: run.shへのフルパスを指定してください
claude mcp add local-rag ~/mcp-local-rag/run.sh \
  -e MCP_WATCH_DIR_1="$HOME/projects/app1" \
  -e MCP_WATCH_DIR_2="$HOME/projects/app2"

# 4. Claude Desktopを再起動
```

### サーバーの停止

```bash
# 停止スクリプトを使用
./stop.sh

# または手動で停止
pkill -f "python.*server.py"
```

### 別の方法：config.jsonを使用

```bash
# 1. config.jsonを編集して監視ディレクトリを設定
vim config.json
# "watch_directories": ["/path/to/project1", "/path/to/project2"],
# "reindex_interval_seconds": 30

# 2. セットアップ（config.jsonの設定を使用）
./setup.sh

# 3. Claude Codeに登録
claude mcp add local-rag /path/to/mcp-local-rag/run.sh
```

### 静音モード（ログ抑制）

```bash
# デバッグログを表示したくない場合
claude mcp add local-rag /path/to/mcp-local-rag/run_quiet.sh \
  -e MCP_WATCH_DIR_1="/path/to/your/project"
```

## 🚀 使い方

### 基本的な使い方

1. **Claude Code内で対話**
   事前に設定したプロジェクトディレクトリが自動的にインデックスされ、検索可能になります。
   
2. **検索例**
   ```
   "Search for authentication implementation"
   "Find files similar to main.py"
   "Get context around line 42 in app.py"
   ```

### 利用可能なコマンド

| コマンド | 説明 |
|---------|------|
| `index_directory` | ディレクトリをインデックス化 |
| `search_codebase` | コードベースを検索 |
| `get_file_context` | ファイルのコンテキストを取得 |
| `find_similar` | 類似ファイルを検索 |
| `watch_directory` | ディレクトリを監視対象に追加 |
| `get_index_status` | インデックスの状態を確認 |

## 🏗️ アーキテクチャ

### データ構造
```
data/index/
├── chroma/               # ChromaDBベクトルデータベース
└── file_metadata.json    # ファイルメタデータ（ハッシュ、インデックス日時）
```

### 技術スタック
- **ベクトルDB**: ChromaDB
- **埋め込みモデル**: Sentence-Transformers (all-MiniLM-L6-v2)
- **ファイル変更検出**: fd（推奨）またはfindコマンド
- **MCPプロトコル**: 標準準拠
- **定期更新**: 30秒ごとの自動再インデックス

## ⚙️ 設定

### 設定 (`config.json`)
```json
{
  "embedding_model": "local",
  "chunk_size": 1000,
  "chunk_overlap": 200,
  "max_file_size": 5242880,
  "embedding_batch_size": 32,
  "similarity_threshold": 0.1,
  "watch_directories": [],
  "reindex_interval_seconds": 30,
  "exclude_dirs": [".git", "node_modules", "venv", ".venv", "__pycache__", "dist", "build", "data"]
}
```

### パフォーマンス設定
- `max_file_size`: 処理する最大ファイルサイズ（デフォルト: 5MB）
- `embedding_batch_size`: 埋め込み生成のバッチサイズ（デフォルト: 32）
- `similarity_threshold`: 検索結果の類似度閾値（デフォルト: 0.1）

### 環境変数での設定
複数のディレクトリを監視する場合：
```bash
MCP_WATCH_DIR_1="/path/to/project1"
MCP_WATCH_DIR_2="/path/to/project2"
MCP_WATCH_DIR_3="/path/to/project3"
```

### 除外ファイル設定 (.mcp-local-rag-ignore)
プロジェクトのルートディレクトリに`.mcp-local-rag-ignore`ファイルを作成することで、
特定のファイルやディレクトリをインデックスから除外できます：

```bash
# 大きなデータファイル
*.json
*.csv
*.db

# バックテスト結果
backtest_results/
results/*.json

# ログファイル
*.log
logs/
```

## 📋 対応ファイル形式

### プログラミング言語
Python, JavaScript, TypeScript, Java, C/C++, Go, Rust, PHP, Ruby, Swift, Kotlin, Scala など

### 設定・ドキュメント
Markdown, JSON, YAML, XML, HTML, CSS など

## 🔧 トラブルシューティング

### インデックスが作成されない
- 監視ディレクトリが設定されているか確認（環境変数またはconfig.json）
- `index_directory`コマンドで手動インデックス
- `watch_directory`コマンドで動的に追加

### 検索結果が表示されない
- `get_index_status`でインデックス状態を確認
- 必要に応じて`index_directory`で再インデックス
- `similarity_threshold`を調整（小さくすると緩い検索）

### メモリ使用量が多い
- `config.json`の`chunk_size`を調整
- `reindex_interval_seconds`を長く設定（デフォルト: 30秒）
- `max_file_size`を小さく設定して大きなファイルを除外

### 処理が遅い
- `.mcp-local-rag-ignore`ファイルで大きなファイルを除外
- `LOGLEVEL=DEBUG`で詳細なタイミング情報を確認
- `test_performance.sh`スクリプトでボトルネックを特定

### fdコマンドが使えない
- fdをインストール（推奨）または findコマンドで代替
- Windowsの場合はWSLまたはGit Bashを使用

## 🚧 将来の機能

### Supervisor機能（計画中）
MCPサーバーの安定性向上のため、以下の機能を検討中：

- **プロセス監視**: MCPサーバープロセスの死活監視
- **自動再起動**: フリーズや異常終了時の自動復旧
- **restart tool**: MCPツールから再起動を実行
- **ヘルスチェック**: 定期的な正常性確認

実装方法：
- シンプルで堅牢な親プロセス（supervisor.py）
- 制御ファイルを使った再起動シグナル
- stdio接続を維持したままの内部リロード

## 🤝 貢献

Pull Requestを歓迎します！

1. このリポジトリをフォーク
2. 機能ブランチを作成 (`git checkout -b feature/amazing-feature`)
3. 変更をコミット (`git commit -m 'Add amazing feature'`)
4. ブランチにプッシュ (`git push origin feature/amazing-feature`)
5. Pull Requestを作成

## 📄 ライセンス

MIT License - 詳細は[LICENSE](LICENSE)を参照

## 🙏 謝辞

- [Anthropic](https://anthropic.com) - Claude & MCP
- [ChromaDB](https://www.trychroma.com) - ベクトルデータベース
- [Sentence-Transformers](https://www.sbert.net) - 埋め込みモデル

## 📞 サポート

問題や質問がある場合は、[Issues](https://github.com/yourusername/mcp-local-rag/issues)でお知らせください。