# SMAPI Improvements Plan

**Created:** 2026-01-08 Session 10
**Status:** In Progress

---

## Overview

Comprehensive improvements to SMAPI GameBridge mod to give the agent better awareness of the game world.

## Priority 1: Water Source Detection (Blocks watering can refill)

**Owner:** Claude
**Files:** `GameStateReader.cs`, `Models/GameState.cs`

### Requirements
- Detect water tiles (ponds, rivers, wells) near player
- Add to `/surroundings` response: nearest water location + distance
- Agent needs this to know where to go when watering can is empty

### Implementation
```csharp
// Add to SurroundingsState
public WaterSourceInfo NearestWater { get; set; }

public class WaterSourceInfo {
    public int X { get; set; }
    public int Y { get; set; }
    public int Distance { get; set; }
    public string Type { get; set; }  // "pond", "river", "well"
}
```

### Detection Method
- `location.isWaterTile(x, y)` - checks for water
- Scan in expanding squares from player position
- Return first water tile found within 20 tiles

---

## Priority 2: Shipping Bin Location

**Owner:** Claude
**Files:** `GameStateReader.cs`, `Models/GameState.cs`

### Requirements
- Find shipping bin on Farm
- Add to `/state` location info: shipping bin coordinates
- Agent needs this to sell harvested crops

### Implementation
```csharp
// Add to LocationState
public TilePosition ShippingBin { get; set; }
```

### Detection Method
- On Farm: Check `Game1.getFarm().getShippingBin()` or scan buildings
- Building type "Shipping Bin" at fixed Farm location (69, 13 on standard farm)

---

## Priority 3: Crop Growth Stage Fix

**Owner:** Claude
**Files:** `GameStateReader.cs`

### Current Bug
- `DaysUntilHarvest` uses `crop.dayOfCurrentPhase` which is days in CURRENT phase
- Need actual total days remaining

### Fix
```csharp
// Calculate actual days until harvest
int totalPhaseDays = crop.phaseDays.Sum();
int daysElapsed = crop.currentPhase.Value; // simplified
int daysRemaining = CalculateActualDaysRemaining(crop);
```

---

## Priority 4: Forageable Detection

**Owner:** Claude
**Files:** `GameStateReader.cs`

### Requirements
- Distinguish forageables from debris
- Spring onion, leek, daffodil, etc. should show as "forageable" not "debris"

### Implementation
- Check `obj.isForage()` or category == -81 (Greens) / -80 (Flowers)
- Add `IsForageable` flag to TileObject

---

## Priority 5: Interactable Objects

**Owner:** Claude
**Files:** `GameStateReader.cs`, `Models/GameState.cs`

### Requirements
- Flag objects that can be interacted with (chests, machines, bins)
- Help agent know what it can use

### Implementation
```csharp
// Add to TileObject
public bool CanInteract { get; set; }
public string InteractionType { get; set; }  // "chest", "machine", "sell"
```

---

## Codex Tasks (UI)

**Owner:** Codex
**Depends on:** SMAPI changes complete

### Task 1: Water Source Indicator (HIGH)
- Show nearest water location on compass/map
- Display distance to water
- Warning when watering can low + water location

### Task 2: Shipping Bin Indicator (MEDIUM)
- Show shipping bin location when player has sellable items
- Could be part of compass or separate indicator

### Task 3: Crop Growth Progress (MEDIUM)
- Update farming progress to show actual days remaining
- Growth stage visualization (seedling → sprout → mature)

---

## Verification Plan

After each SMAPI change:
1. Build mod: `dotnet build -c Release`
2. Restart game
3. Test endpoint: `curl localhost:8790/state | jq .`
4. Verify new data appears correctly

Final integration test:
1. Start fresh Day 1
2. Agent plants seeds (tests tillability fix)
3. Agent waters crops (tests tool detection)
4. Agent refills watering can (tests water source detection)
5. Agent harvests and sells (tests shipping bin)

---

## Execution Order

1. **Claude NOW:** Water source + shipping bin + crop fix (SMAPI)
2. **Claude:** Forageable + interactable (SMAPI)
3. **Claude:** Update Python agent to use new data
4. **Codex:** UI updates for new data
5. **All:** Integration test

---

*Plan created Session 10. Executing immediately.*
