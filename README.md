# MCP Local RAG 🚀

プロジェクトごとに独立したインデックスを持つ、ローカルファイルRAGシステム。
[Claude Code](https://claude.ai/code)のMCP（Model Context Protocol）サーバーとして動作します。

## ✨ 特徴

### 🎯 プロジェクト自動認識
- 作業ディレクトリを自動検出
- プロジェクトごとに独立したインデックス
- コンテキストに応じた検索結果

### 🔄 リアルタイム同期
- ファイル変更を自動検知
- インデックスを即座に更新
- 常に最新のコードベースを検索

### 🔍 高度な検索
- セマンティック検索
- 類似ファイル検索
- コンテキスト抽出

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
# 現在のディレクトリをインデックス
./setup.sh .

# または複数のプロジェクトを一度にインデックス
./setup.sh /path/to/project1 /path/to/project2

# 3. Claude Codeに登録（環境変数でディレクトリを指定）
claude mcp add local-rag $(pwd)/run.sh \
  -e MCP_WATCH_DIR_1="/path/to/project1" \
  -e MCP_WATCH_DIR_2="/path/to/project2"

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
# "auto_index": {
#   "watch_directories": ["/path/to/project1", "/path/to/project2"]
# }

# 2. セットアップ（config.jsonの設定を使用）
./setup.sh

# 3. Claude Codeに登録
claude mcp add local-rag $(pwd)/run.sh
```

### 静音モード（ログ抑制）

```bash
# デバッグログを表示したくない場合
claude mcp add local-rag $(pwd)/run_quiet.sh \
  -e MCP_WATCH_DIR_1="$(pwd)"
```

## 🚀 使い方

### 基本的な使い方

1. **プロジェクトディレクトリに移動**
   ```bash
   cd /path/to/your/project
   ```
   自動的にプロジェクトとして認識され、専用のインデックスが作成されます。

2. **Claude Code内で検索**
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

### プロジェクト分離
```
data/index/
├── chroma/
│   ├── project_app1/     # プロジェクト1専用
│   ├── project_app2/     # プロジェクト2専用
│   └── project_app3/     # プロジェクト3専用
└── projects.json         # プロジェクト管理
```

### 技術スタック
- **ベクトルDB**: ChromaDB
- **埋め込みモデル**: 
  - OpenAI text-embedding-3-small
  - Sentence-Transformers (ローカル)
- **ファイル監視**: Watchdog
- **MCPプロトコル**: 標準準拠

## ⚙️ 設定

### グローバル設定 (`config.json`)
```json
{
  "embedding_model": "local",
  "chunk_size": 1000,
  "chunk_overlap": 200,
  "auto_index": {
    "enabled": true,
    "auto_discover": true,
    "max_projects": 3
  }
}
```

### プロジェクト設定 (`.mcp-rag.json`) - 🚧 今後実装予定
プロジェクトごとの個別設定機能（現在未実装）：
```json
{
  "name": "My Project",
  "index_settings": {
    "chunk_size": 1500,
    "additional_exclude": ["tests/", "*.generated.ts"]
  }
}
```
*注: 現在はconfig.jsonのグローバル設定のみ有効です*

## 📋 対応ファイル形式

### プログラミング言語
Python, JavaScript, TypeScript, Java, C/C++, Go, Rust, PHP, Ruby, Swift, Kotlin, Scala など

### 設定・ドキュメント
Markdown, JSON, YAML, XML, HTML, CSS など

## 🔧 トラブルシューティング

### インデックスが作成されない
- プロジェクトマーカー（`.git`, `package.json`, `requirements.txt`）を確認
- `watch_directory`コマンドで手動登録

### 検索結果が表示されない
- `get_index_status`でインデックス状態を確認
- 必要に応じて`index_directory`で再インデックス

### メモリ使用量が多い
- `config.json`の`chunk_size`を調整
- ローカル埋め込みモデルを軽量版に変更

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