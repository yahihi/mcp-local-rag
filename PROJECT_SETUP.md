# プロジェクトごとのRAG設定ガイド

## 問題と解決策

### 従来の問題点
- すべてのプロジェクトが同じデータベースに混在
- コンテキストの切り替えができない
- 異なるプロジェクトのコードが混ざって検索される

### 新しい解決策
- **プロジェクトごとに独立したコレクション**を作成
- **自動的に作業ディレクトリを検出**
- **プロジェクト設定ファイル**で細かい制御

## セットアップ方法

### 1. 自動検出（推奨）

作業ディレクトリに移動するだけで自動的にプロジェクトとして認識されます：

```bash
cd /path/to/your/project
# MCPサーバーが自動的にプロジェクトを検出・登録
```

### 2. 手動登録

特定のディレクトリをプロジェクトとして登録：

```
"Use mcp-local-rag to register project /path/to/project"
```

### 3. プロジェクト設定ファイル

プロジェクトルートに `.mcp-rag.json` を作成して詳細設定：

```json
{
  "name": "My Project",
  "description": "プロジェクトの説明",
  "index_settings": {
    "chunk_size": 1000,
    "chunk_overlap": 200,
    "additional_exclude": [
      "tests/fixtures",
      "*.generated.ts"
    ]
  },
  "watch_settings": {
    "enabled": true,
    "auto_index": true
  }
}
```

## 使用例

### プロジェクトの切り替え

```bash
# プロジェクトAで作業
cd ~/projects/project-a
# 「authentication」を検索 → project-aのコードのみ検索

# プロジェクトBに切り替え
cd ~/projects/project-b  
# 「authentication」を検索 → project-bのコードのみ検索
```

### プロジェクト一覧の確認

```
"Use mcp-local-rag to list all projects"
```

### 現在のプロジェクトの確認

```
"Use mcp-local-rag to show current project"
```

### クロスプロジェクト検索

複数のプロジェクトを横断して検索：

```
"Use mcp-local-rag to search 'database connection' across all projects"
```

## データ構造

```
data/index/
├── chroma/                    # ChromaDBデータ
│   ├── project_myapp/         # プロジェクトごとのコレクション
│   ├── project_backend/
│   └── project_frontend/
├── projects.json              # プロジェクト登録情報
└── watch_config.json          # 監視設定
```

## 利点

1. **データの分離** - プロジェクトごとに独立したインデックス
2. **高速検索** - 不要なプロジェクトを検索しない
3. **コンテキスト認識** - 現在の作業に関連する結果のみ
4. **柔軟な設定** - プロジェクトごとに最適化可能

## トラブルシューティング

### プロジェクトが認識されない
- `.git`、`package.json`、`requirements.txt`などのマーカーファイルがあることを確認
- 手動で登録: `register project /path/to/project`

### 検索結果が混在する
- `list projects`で現在のプロジェクトを確認
- 必要に応じてコレクションをリセット

### インデックスのリセット
```
"Use mcp-local-rag to reset index for current project"
```