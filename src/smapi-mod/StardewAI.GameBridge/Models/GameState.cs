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
    public List<ResourceClumpInfo> ResourceClumps { get; set; } = new();
}

/// <summary>Large obstacles that need tool upgrades (stumps, logs, boulders)</summary>
public class ResourceClumpInfo
{
    public int X { get; set; }
    public int Y { get; set; }
    public int Width { get; set; }
    public int Height { get; set; }
    public string Type { get; set; }           // "Stump", "Log", "Boulder", "Meteorite"
    public string RequiredTool { get; set; }   // "Copper Axe", "Steel Axe", "Steel Pickaxe", etc.
    public int Health { get; set; }
}

/// <summary>Result of pathfinding check</summary>
public class PathCheckResult
{
    public bool Reachable { get; set; }
    public int PathLength { get; set; }
    public List<TilePosition> Path { get; set; }
}

/// <summary>Result of tile passability check</summary>
public class PassableResult
{
    public int X { get; set; }
    public int Y { get; set; }
    public bool Passable { get; set; }
    public string Blocker { get; set; }
}

/// <summary>Result of area passability scan</summary>
public class PassableAreaResult
{
    public int CenterX { get; set; }
    public int CenterY { get; set; }
    public int Radius { get; set; }
    public List<PassableResult> Tiles { get; set; } = new();
}

/// <summary>Player skill levels and professions</summary>
public class SkillsState
{
    public SkillInfo Farming { get; set; }
    public SkillInfo Fishing { get; set; }
    public SkillInfo Mining { get; set; }
    public SkillInfo Combat { get; set; }
    public SkillInfo Foraging { get; set; }
    public SkillInfo Luck { get; set; }
}

/// <summary>Individual skill information</summary>
public class SkillInfo
{
    public int Level { get; set; }
    public int Xp { get; set; }
    public int XpToNextLevel { get; set; }
    public string Profession5 { get; set; }   // Profession chosen at level 5
    public string Profession10 { get; set; }  // Profession chosen at level 10
}

// ============================================
// NPC & RELATIONSHIP ENDPOINTS
// ============================================

/// <summary>All NPCs in the game world</summary>
public class NpcsState
{
    public List<NpcDetails> Npcs { get; set; } = new();
}

/// <summary>Detailed NPC information</summary>
public class NpcDetails
{
    public string Name { get; set; }
    public string DisplayName { get; set; }
    public string Location { get; set; }
    public int TileX { get; set; }
    public int TileY { get; set; }
    public bool IsVillager { get; set; }
    public bool CanSocialize { get; set; }
    public int FriendshipPoints { get; set; }
    public int FriendshipHearts { get; set; }
    public bool CanDate { get; set; }
    public bool IsDating { get; set; }
    public bool IsMarried { get; set; }
    public string BirthdaySeason { get; set; }
    public int BirthdayDay { get; set; }
    public bool IsBirthdayToday { get; set; }
    public bool GiftedToday { get; set; }
    public int GiftsThisWeek { get; set; }
}

// ============================================
// ANIMAL ENDPOINTS
// ============================================

/// <summary>All animals on the farm</summary>
public class AnimalsState
{
    public List<AnimalDetails> Animals { get; set; } = new();
    public List<BuildingDetails> Buildings { get; set; } = new();
}

/// <summary>Individual animal information</summary>
public class AnimalDetails
{
    public long Id { get; set; }
    public string Name { get; set; }
    public string Type { get; set; }           // Cow, Chicken, Pig, etc.
    public string BuildingName { get; set; }   // Which barn/coop
    public int TileX { get; set; }
    public int TileY { get; set; }
    public bool IsOutside { get; set; }
    public int Happiness { get; set; }         // 0-255
    public int Friendship { get; set; }        // 0-1000
    public bool WasPetToday { get; set; }
    public bool ProducedToday { get; set; }    // Has product ready
    public string CurrentProduct { get; set; } // Egg, Milk, Wool, etc.
    public int Age { get; set; }               // Days old
}

/// <summary>Barn/Coop building information</summary>
public class BuildingDetails
{
    public string Type { get; set; }           // Barn, Coop, Big Barn, etc.
    public string Name { get; set; }
    public int TileX { get; set; }
    public int TileY { get; set; }
    public int AnimalCount { get; set; }
    public int MaxAnimals { get; set; }
    public bool DoorOpen { get; set; }
}

// ============================================
// MACHINE/ARTISAN ENDPOINTS
// ============================================

/// <summary>All processing machines</summary>
public class MachinesState
{
    public List<MachineDetails> Machines { get; set; } = new();
}

/// <summary>Individual machine information</summary>
public class MachineDetails
{
    public string Name { get; set; }
    public string Location { get; set; }
    public int TileX { get; set; }
    public int TileY { get; set; }
    public bool IsProcessing { get; set; }
    public string InputItem { get; set; }      // What's being processed
    public string OutputItem { get; set; }     // What it will produce
    public int MinutesUntilReady { get; set; }
    public bool ReadyForHarvest { get; set; }
    public bool NeedsInput { get; set; }       // Empty and ready for input
}

// ============================================
// CALENDAR ENDPOINTS
// ============================================

/// <summary>Calendar and event information</summary>
public class CalendarState
{
    public string Season { get; set; }
    public int Day { get; set; }
    public int Year { get; set; }
    public string DayOfWeek { get; set; }
    public int DaysUntilSeasonEnd { get; set; }
    public string TodayEvent { get; set; }     // Festival or event today
    public List<CalendarEvent> UpcomingEvents { get; set; } = new();
    public List<CalendarEvent> UpcomingBirthdays { get; set; } = new();
}

/// <summary>Calendar event</summary>
public class CalendarEvent
{
    public int Day { get; set; }
    public string Season { get; set; }
    public string Name { get; set; }
    public string Location { get; set; }
    public string Type { get; set; }           // festival, birthday, etc.
}

// ============================================
// FISHING ENDPOINTS
// ============================================

/// <summary>Fishing information for current location</summary>
public class FishingState
{
    public string Location { get; set; }
    public string Weather { get; set; }
    public string Season { get; set; }
    public int TimeOfDay { get; set; }
    public List<FishDetails> AvailableFish { get; set; } = new();
}

/// <summary>Fish that can be caught</summary>
public class FishDetails
{
    public string Name { get; set; }
    public int Difficulty { get; set; }        // 5-110
    public string Behavior { get; set; }       // Mixed, Smooth, Sinker, Floater, Dart
    public int MinSize { get; set; }
    public int MaxSize { get; set; }
    public int BasePrice { get; set; }
    public string TimeRange { get; set; }      // "6am-7pm" or "Any"
    public string WeatherRequired { get; set; } // "Any", "Sunny", "Rainy"
}

// ============================================
// MINING ENDPOINTS
// ============================================

/// <summary>Mine floor information</summary>
public class MiningState
{
    public string Location { get; set; }       // Mine, Skull Cavern, etc.
    public int Floor { get; set; }
    public string FloorType { get; set; }      // normal, frozen, lava, etc.
    public bool LadderFound { get; set; }
    public bool ShaftFound { get; set; }
    public List<MineObject> Rocks { get; set; } = new();
    public List<MineMonster> Monsters { get; set; } = new();
}

/// <summary>Rock/ore in the mine</summary>
public class MineObject
{
    public int TileX { get; set; }
    public int TileY { get; set; }
    public string Type { get; set; }           // Stone, Copper, Iron, Gold, Iridium, Gem
    public int Health { get; set; }            // Hits to break
}

/// <summary>Monster in the mine</summary>
public class MineMonster
{
    public string Name { get; set; }
    public int TileX { get; set; }
    public int TileY { get; set; }
    public int Health { get; set; }
    public int MaxHealth { get; set; }
    public int Damage { get; set; }
}

// ============================================
// STORAGE ENDPOINTS
// ============================================

/// <summary>All storage containers</summary>
public class StorageState
{
    public List<ChestDetails> Chests { get; set; } = new();
    public List<InventoryItem> Fridge { get; set; } = new();
    public int SiloHay { get; set; }
    public int SiloCapacity { get; set; }
}

/// <summary>Chest contents</summary>
public class ChestDetails
{
    public string Location { get; set; }
    public int TileX { get; set; }
    public int TileY { get; set; }
    public string Color { get; set; }
    public List<InventoryItem> Items { get; set; } = new();
}
