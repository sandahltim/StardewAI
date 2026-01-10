# Code Style & Conventions

## Python

### General Style
- Follow **PEP 8** with 4-space indentation
- Line length: ~100 characters (soft limit)
- Use **type hints** for function signatures and class attributes
- Use `dataclasses` for data structures

### Naming
- `snake_case` for files, functions, variables: `unified_agent.py`, `capture_screen()`
- `PascalCase` for classes: `UnifiedVLM`, `StardewAgent`, `ModBridgeController`
- `UPPER_CASE` for constants: `CARDINAL_DIRECTIONS`, `HAS_GAMEPAD`
- Private methods: `_prefix_with_underscore()`

### Example Class Structure
```python
@dataclass
class Config:
    server_url: str
    model: str
    request_timeout: float = 60.0
    
    @staticmethod
    def from_yaml(path: str) -> "Config":
        ...

class UnifiedVLM:
    def __init__(self, config: Config):
        self.config = config
        self.client = httpx.Client(timeout=config.request_timeout)
    
    def capture_screen(self) -> Image.Image:
        ...
    
    def _repair_json(self, text: str) -> str:
        ...
```

### Imports
- Standard library first, then third-party, then local
- Group with blank lines between sections
- Use try/except for optional dependencies with flags:
```python
try:
    import vgamepad as vg
    HAS_GAMEPAD = True
except ImportError:
    HAS_GAMEPAD = False
```

### Documentation
- Minimal inline comments (only for non-obvious logic)
- No docstrings required (AI-first codebase)
- Document in markdown files instead (`docs/`)

## Shell Scripts

- `kebab-case` for filenames: `start-llama-server.sh`
- Include shebang: `#!/bin/bash`
- Set error handling: `set -e`

## YAML Configuration

- `lowercase_underscore` for keys
- Comments for sections with `# =====` separators
- Example:
```yaml
server:
  url: "http://localhost:8780"
  api_type: "llama_cpp"

timing:
  think_interval: 2.0
  action_delay: 0.3
```

## C# (SMAPI Mod)

- Standard .NET conventions
- `PascalCase` for public members
- `_camelCase` for private fields
- XML documentation comments for public APIs

## File Organization

- Group by feature/domain (`memory/`, `skills/`, `commentary/`)
- Keep shared utilities minimal
- Tests named `test_*.py` in same directory as code being tested
