# Task Completion Checklist

When completing a task in StardewAI, follow this checklist:

## 1. Code Quality

- [ ] Code follows PEP 8 style (Python) or .NET conventions (C#)
- [ ] Type hints added for new functions/methods
- [ ] No unnecessary abstractions - keep it simple
- [ ] Existing patterns followed (check similar code first)

## 2. Testing

No formal test framework - manual verification:

- [ ] Test the specific functionality added/changed
- [ ] For agent changes: Run `python src/python-agent/unified_agent.py --observe` to verify
- [ ] For SMAPI mod: Test with `curl http://localhost:8790/health`
- [ ] For UI: Verify at `http://localhost:9001`

### Quick Test Commands
```bash
source venv/bin/activate
python src/python-agent/unified_agent.py --observe --goal "Test goal"
```

## 3. Documentation

- [ ] Update `docs/NEXT_SESSION.md` with changes made
- [ ] Update `docs/SESSION_LOG.md` if significant progress
- [ ] Update `CLAUDE.md` if architecture changed
- [ ] Update `docs/SETUP.md` if new dependencies or setup steps

## 4. Configuration

- [ ] If config keys added, update `config/settings.yaml`
- [ ] Document new config options in settings file comments

## 5. Before Committing

- [ ] Verify Git status: `git status`
- [ ] Stage only relevant files: `git add <files>`
- [ ] Write descriptive commit message
- [ ] **NEVER commit without explicit approval from Tim**
- [ ] **NEVER push to remote without explicit approval**

## 6. Team Communication

For significant changes:
- [ ] Post update to team chat: `./scripts/team_chat.py post claude "Completed: [task]"`
- [ ] Update `docs/CODEX_TASKS.md` if delegating to Codex
- [ ] Note blockers in `docs/TEAM_PLAN.md` if any

## 7. Session End

At end of work session:
- [ ] Update `docs/NEXT_SESSION.md` with:
  - What was completed
  - Current state
  - Next steps
  - Files changed
- [ ] List any services that should be running
- [ ] Include quick start commands for next session
