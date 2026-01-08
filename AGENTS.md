# Repository Guidelines

## Project Structure & Module Organization
- `src/python-agent/`: Core agent code. `unified_agent.py` is the active unified VLM implementation; `agent.py` is the legacy dual-model reference.
- `config/`: Runtime settings (notably `config/settings.yaml` for server URL, model selection, mode, and prompts).
- `docs/`: Architecture, setup, and session notes. Keep these current when behavior changes.
- `scripts/`: Operational scripts like `scripts/start-llama-server.sh` for the local llama.cpp server.
- `models/`: Local GGUF model files and vision encoders (mmproj).
- `logs/`: Runtime logs and screenshots (created at runtime).

## Team Roles & Communication
- **Project Manager:** Claude (Opus) owns task assignment, architecture decisions, and coordination.
- **Codex:** UI/memory implementation and state persistence.
- **Human Lead:** Tim provides direction, testing, and final decisions.
- **Team chat:** `http://localhost:9001/api/team` or `scripts/team_chat.py` for status updates and questions.
- **Task docs:** `docs/CODEX_TASKS.md` (Codex queue), `docs/CLAUDE_TASKS.md` (Claude queue), `docs/TEAM_PLAN.md` (sprint plan), `docs/SESSION_LOG.md` (progress notes).

## Build, Test, and Development Commands
- Activate environment: `source venv/bin/activate`
- Start the model server: `./scripts/start-llama-server.sh Qwen3VL-30B-A3B`
- Run unified agent (co-op): `python src/python-agent/unified_agent.py --mode coop --goal "Help with farming"`
- Run unified agent (helper): `python src/python-agent/unified_agent.py --mode helper --goal "Give farming advice"`
- Legacy vision test: `python src/python-agent/test_vision.py`

## Coding Style & Naming Conventions
- Python style: follow PEP 8 with 4-space indentation.
- Filenames: snake_case for scripts (`unified_agent.py`), kebab-case for shell scripts (`start-llama-server.sh`).
- Config keys: lowercase with underscores in `config/settings.yaml`.

## Testing Guidelines
- No formal test framework is configured. Use the scripts in `src/python-agent/` as manual smoke tests.
- When adding new scripts, name them `test_*.py` and keep them runnable from the repo root.

## Commit & Pull Request Guidelines
- No strict commit convention is enforced; keep messages short and descriptive (e.g., "Fix unified agent port" or "Update setup docs").
- For PRs, include a concise summary, any relevant config changes, and the exact commands used to validate behavior.

## Configuration & Safety Notes
- The unified llama.cpp server runs on port `8780`. Keep this consistent across code and docs.
- Co-op mode uses a virtual Xbox controller via `vgamepad`; helper mode is advisory only.
- Do not modify anything under `/Gary/`; this repo is isolated by design.
