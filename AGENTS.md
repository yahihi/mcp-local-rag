# Repository Guidelines

## Project Structure & Module Organization
- `src/`: Core library modules (`embeddings.py`, `indexer.py`, `search.py`, `utils.py`, `vectordb.py`).
- `server.py`: MCP server entrypoint used by `run.sh`/`run_quiet.sh`.
- `tests/`: Pytest suite (`tests/test_*.py`).
- `scripts/`: Utilities (`setup_index.py`, `debug_chroma.py`).
- `data/`: Local vector index and metadata (generated at runtime).
- `config.json`: Server configuration (watch paths, intervals, excludes).

## Build, Test, and Development Commands
- Install (dev): `uv pip install -r requirements.txt`.
- Setup index: `./setup.sh [DIR ...]` (downloads model, builds initial index).
- Run server: `./run.sh` (normal) or `./run_quiet.sh` (suppressed logs).
- Stop server: `./stop.sh` or `pkill -f "python.*server.py"`.
- Test: `uv run python -m unittest discover tests/` (67 tests).

## Coding Style & Naming Conventions
- Python 3.10+, 4-space indent, type hints required in new/changed code.
- Naming: `snake_case` for modules/functions, `PascalCase` for classes, `UPPER_CASE` for constants.
- Formatting: Black (line length 88). Run: `uv run black src tests`.
- Type checking: `uv run mypy src`.

## Testing Guidelines
- Framework: unittest (Python standard library); place tests in `tests/` as `test_*.py` with clear, isolated cases.
- Test coverage includes: `indexer`, `search`, `vectordb`, `embeddings`, and `file_watcher` logic.
- Run tests: `uv run python -m unittest discover tests/` (all 67 tests should pass).
- Run quickly and deterministically; avoid external network or large I/O.

## Commit & Pull Request Guidelines
- Conventional Commits: `feat:`, `fix:`, `docs:`, etc.
  - Examples: `feat: add project-scoped collections`, `fix: handle SIGTERM loop`, `docs: update README for fd usage`.
- PRs must include: purpose/summary, linked issue(s), manual test notes (commands/log snippets), and confirm all tests pass (`uv run python -m unittest discover tests/`).

## Security & Configuration Tips
- Avoid indexing secrets; use `.gitignore`-aware scanning with `fd` when possible.
- Configure watch paths via `config.json` or environment vars `MCP_WATCH_DIR_1..N`.
- Default embeddings are local; no API keys required. If adding providers, use env vars—never commit keys.

## MCP/Agent Notes
- Register with Claude Code: `claude mcp add local-rag /path/to/repo/run.sh`.
- For targeted debugging, run directly: `uv run --no-project python server.py`.
