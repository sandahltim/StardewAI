# Suggested Commands

## Run Agent
```bash
cd /home/tim/StardewAI
source venv/bin/activate
python src/python-agent/unified_agent.py --goal "Water the crops"
```

## Run Tests
```bash
pytest src/python-agent/tests/
pytest src/python-agent/tests/test_farm_surveyor.py -v
```

## Check Game State
```bash
curl -s localhost:8790/state | jq .
curl -s localhost:8790/surroundings | jq .
curl -s localhost:8790/farm | jq .
```

## Debug Cell Farming
```bash
python unified_agent.py --goal "Plant parsnip seeds" 2>&1 | grep -E "🌱|Complete|Cell \("
```

## Git
```bash
git status
git add -A && git commit -m "message"
```
