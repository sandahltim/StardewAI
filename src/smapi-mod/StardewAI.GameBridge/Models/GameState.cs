namespace StardewAI.GameBridge.Models;

/// <summary>Complete game state snapshot for AI agent</summary>
public class GameState
{
    public long Tick { get; set; }
    public PlayerState Player { get; set; }
    public TimeState Time { get; set; }
    public LocationState Location { get; set; }
    public Dictionary<string, LandmarkInfo> Landmarks { get; set; } = new();
    public List<InventoryItem> Inventory { get; set; } = new();

    // UI state - for detecting popups, menus, events
    public string Menu { get; set; }        // Active menu type (null if none)
    public string Event { get; set; }       // Active event/cutscene (null if none)
    public bool DialogueUp { get; set; }    // True if dialogue box is showing
    public bool Paused { get; set; }        // True if game is paused
}

/// <summary>Player position, energy, tools</summary>
public class PlayerState
{
    public string Name { get; set; }
    public int TileX { get; set; }
    public int TileY { get; set; }
    public int PixelX { get; set; }
    public int PixelY { get; set; }
    public int FacingDirection { get; set; } // 0=north, 1=east, 2=south, 3=west
    public string Facing { get; set; } // Cardinal direction: "north", "east", "south", "west"
    public int Energy { get; set; }
    public int MaxEnergy { get; set; }
    public int Health { get; set; }
    public int MaxHealth { get; set; }
    public int Money { get; set; }
    public string CurrentTool { get; set; }
    public int CurrentToolIndex { get; set; }
    public bool IsMoving { get; set; }
    public bool CanMove { get; set; }
    // Watering can state
    public int WateringCanWater { get; set; }  // Current water level
    public int WateringCanMax { get; set; }    // Max capacity (40 for basic can)
}

/// <summary>In-game time and date</summary>
public class TimeState
{
    public int Hour { get; set; }       // 6-26 (2am shown as 26)
    public int Minute { get; set; }     // 0, 10, 20, 30, 40, 50
    public string TimeString { get; set; } // "7:30 AM"
    public string Season { get; set; }  // spring, summer, fall, winter
    public int Day { get; set; }        // 1-28
    public int Year { get; set; }
    public string DayOfWeek { get; set; }
    public string Weather { get; set; } // sunny, rainy, stormy, snowy
}

/// <summary>Current location info</summary>
public class LocationState
{
    public string Name { get; set; }
    public string DisplayName { get; set; }
    public bool IsOutdoors { get; set; }
    public bool IsFarm { get; set; }
    public int MapWidth { get; set; }
    public int MapHeight { get; set; }
    public TilePosition ShippingBin { get; set; }  // Location of shipping bin (Farm only)
    public List<TileObject> Objects { get; set; } = new();
    public List<NpcInfo> Npcs { get; set; } = new();
    public List<CropInfo> Crops { get; set; } = new();
}

/// <summary>Object on a tile (stone, wood, chest, etc.)</summary>
public class TileObject
{
    public int X { get; set; }
    public int Y { get; set; }
    public string Name { get; set; }
    public string Type { get; set; }
    public bool IsPassable { get; set; }
    public bool IsForageable { get; set; }    // Can be picked up (spring onion, leek, etc.)
    public bool CanInteract { get; set; }     // Can interact with (chest, machine, etc.)
    public string InteractionType { get; set; } // "chest", "machine", "sell", null
}

/// <summary>NPC information</summary>
public class NpcInfo
{
    public string Name { get; set; }
    public int TileX { get; set; }
    public int TileY { get; set; }
    public bool IsVillager { get; set; }
    public int Friendship { get; set; }
}

/// <summary>Crop on farmland</summary>
public class CropInfo
{
    public int X { get; set; }
    public int Y { get; set; }
    public string CropName { get; set; }
    public int DaysUntilHarvest { get; set; }
    public bool IsWatered { get; set; }
    public bool IsReadyForHarvest { get; set; }
}

/// <summary>Inventory item</summary>
public class InventoryItem
{
    public int Slot { get; set; }
    public string Name { get; set; }
    public string Type { get; set; } // tool, seed, crop, object
    public int Stack { get; set; }
    public int Quality { get; set; }
}

/// <summary>Directional surroundings snapshot</summary>
public class SurroundingsState
{
    public TilePosition Position { get; set; }
    public CurrentTileInfo CurrentTile { get; set; }
    public Dictionary<string, DirectionInfo> Directions { get; set; } = new();
    public WaterSourceInfo NearestWater { get; set; }  // Closest water for refilling watering can
}

/// <summary>Nearest water source for refilling watering can</summary>
public class WaterSourceInfo
{
    public int X { get; set; }
    public int Y { get; set; }
    public int Distance { get; set; }      // Manhattan distance from player
    public string Direction { get; set; }  // General direction: "north", "south", "east", "west", "here"
}

/// <summary>Landmark relative info</summary>
public class LandmarkInfo
{
    public int Distance { get; set; }
    public string Direction { get; set; }  // "north", "south", "east", "west", "northeast", etc.
}

/// <summary>What's on the player's current tile</summary>
public class CurrentTileInfo
{
    public string State { get; set; }  // "clear", "debris", "tilled", "planted", "watered"
    public string Object { get; set; } // null, "Weeds", "Stone", "Twig", crop name, etc.
    public bool CanTill { get; set; }  // true if hoe can be used here
    public bool CanPlant { get; set; } // true if seeds can be planted here
}

/// <summary>Simple tile position</summary>
public class TilePosition
{
    public int X { get; set; }
    public int Y { get; set; }
}

/// <summary>Directional scan information</summary>
public class DirectionInfo
{
    public bool Clear { get; set; }
    public int TilesUntilBlocked { get; set; }
    public string Blocker { get; set; }
}

/// <summary>Farm state - accessible from any location for planning</summary>
public class FarmState
{
    public string Name { get; set; }
    public int MapWidth { get; set; }
    public int MapHeight { get; set; }
    public TilePosition ShippingBin { get; set; }
    public List<CropInfo> Crops { get; set; } = new();
    public List<TileObject> Objects { get; set; } = new();
    public List<TilePosition> TilledTiles { get; set; } = new();
}
