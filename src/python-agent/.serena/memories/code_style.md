# Code Style

## Python Conventions
- Type hints for function parameters and returns
- Dataclasses for data structures
- Logging with emoji prefixes (🌱 for cell farming, 🎯 for tasks)
- Underscore prefix for private methods (_method_name)

## Design Patterns
- Coordinator pattern for orchestration (CellFarmingCoordinator)
- Surveyor pattern for planning (FarmSurveyor)
- State machine for task execution

## Logging
- INFO level for user-visible progress
- DEBUG level for detailed tracing
- Use structured logging with context

## Testing
- pytest for unit tests
- Mock game state as dicts
