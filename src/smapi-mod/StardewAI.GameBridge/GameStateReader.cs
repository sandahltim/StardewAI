using Microsoft.Xna.Framework;
using StardewAI.GameBridge.Models;
using StardewModdingAPI;
using StardewValley;
using StardewValley.Buildings;
using StardewValley.TerrainFeatures;

namespace StardewAI.GameBridge;

/// <summary>
/// Reads game state from Stardew Valley.
/// Must be called from the game's main thread (via UpdateTicked event).
/// </summary>
public class GameStateReader
{
    private readonly IMonitor _monitor;

    public GameStateReader(IMonitor monitor)
    {
        _monitor = monitor;
    }

    /// <summary>Read complete game state snapshot</summary>
    public GameState ReadState()
    {
        if (!Context.IsWorldReady || Game1.player == null)
            return null;

        return new GameState
        {
            Tick = Game1.ticks,
            Player = ReadPlayerState(),
            Time = ReadTimeState(),
            Location = ReadLocationState(),
            Inventory = ReadInventory()
        };
    }

    /// <summary>Read immediate surroundings in each direction (up to N tiles).</summary>
    public SurroundingsState ReadSurroundings(int maxTiles = 5)
    {
        if (!Context.IsWorldReady || Game1.player == null)
            return null;

        var player = Game1.player;
        var location = player.currentLocation;
        if (location == null) return null;

        int mapWidth = location.Map?.Layers[0]?.LayerWidth ?? 0;
        int mapHeight = location.Map?.Layers[0]?.LayerHeight ?? 0;
        var start = player.TilePoint;

        // Check current tile state for farming
        var facingDir = player.FacingDirection;
        int frontX = start.X + (facingDir == 1 ? 1 : facingDir == 3 ? -1 : 0);
        int frontY = start.Y + (facingDir == 2 ? 1 : facingDir == 0 ? -1 : 0);
        var currentTile = GetTileState(location, frontX, frontY);

        return new SurroundingsState
        {
            Position = new TilePosition { X = start.X, Y = start.Y },
            CurrentTile = currentTile,
            Directions = new Dictionary<string, DirectionInfo>
            {
                ["up"] = ScanDirection(location, start.X, start.Y, 0, -1, maxTiles, mapWidth, mapHeight),
                ["down"] = ScanDirection(location, start.X, start.Y, 0, 1, maxTiles, mapWidth, mapHeight),
                ["left"] = ScanDirection(location, start.X, start.Y, -1, 0, maxTiles, mapWidth, mapHeight),
                ["right"] = ScanDirection(location, start.X, start.Y, 1, 0, maxTiles, mapWidth, mapHeight)
            }
        };
    }

    private CurrentTileInfo GetTileState(GameLocation location, int x, int y)
    {
        var tileVec = new Microsoft.Xna.Framework.Vector2(x, y);
        var result = new CurrentTileInfo
        {
            State = "clear",
            Object = null,
            CanTill = false,
            CanPlant = false
        };

        // Check for objects on the tile
        if (location.Objects.TryGetValue(tileVec, out var obj))
        {
            result.Object = obj.Name;
            result.State = "debris";
            return result;
        }

        // Check for terrain features (grass, trees, etc.)
        if (location.terrainFeatures.TryGetValue(tileVec, out var feature))
        {
            if (feature is StardewValley.TerrainFeatures.HoeDirt hoeDirt)
            {
                if (hoeDirt.crop != null)
                {
                    result.State = hoeDirt.state.Value == 1 ? "watered" : "planted";
                    result.Object = !string.IsNullOrEmpty(hoeDirt.crop.indexOfHarvest.Value) ? "crop" : "seed";
                }
                else
                {
                    result.State = hoeDirt.state.Value == 1 ? "watered" : "tilled";
                    result.CanPlant = true;
                }
                return result;
            }
            else if (feature is StardewValley.TerrainFeatures.Grass)
            {
                result.State = "debris";
                result.Object = "Grass";
                return result;
            }
            else if (feature is StardewValley.TerrainFeatures.Tree)
            {
                result.State = "debris";
                result.Object = "Tree";
                return result;
            }
        }

        // Check if tillable
        result.CanTill = location.doesTileHaveProperty(x, y, "Diggable", "Back") != null
                         || (location is StardewValley.Farm);
        if (result.CanTill)
        {
            result.State = "clear";
        }

        return result;
    }

    private DirectionInfo ScanDirection(
        GameLocation location,
        int startX,
        int startY,
        int dx,
        int dy,
        int maxTiles,
        int mapWidth,
        int mapHeight)
    {
        int tilesClear = 0;
        string blocker = null;

        for (int i = 1; i <= maxTiles; i++)
        {
            int x = startX + dx * i;
            int y = startY + dy * i;

            if (x < 0 || y < 0 || x >= mapWidth || y >= mapHeight)
            {
                blocker = "map_edge";
                break;
            }

            var tileLocation = new xTile.Dimensions.Location(x, y);
            var tileVec = new Vector2(x, y);
            // Check passability and object/feature occupation
            if (!location.isTilePassable(tileLocation, Game1.viewport) ||
                location.objects.ContainsKey(tileVec) ||
                (location.terrainFeatures.TryGetValue(tileVec, out var tf) && !tf.isPassable()))
            {
                blocker = GetBlockerName(location, x, y);
                break;
            }

            tilesClear++;
        }

        return new DirectionInfo
        {
            Clear = blocker == null,
            TilesUntilBlocked = tilesClear,
            Blocker = blocker
        };
    }

    private string GetBlockerName(GameLocation location, int x, int y)
    {
        var tile = new Vector2(x, y);
        foreach (var character in location.characters)
        {
            if (character.TilePoint.X == x && character.TilePoint.Y == y)
            {
                return character.displayName ?? character.Name;
            }
        }

        if (location.objects.TryGetValue(tile, out var obj))
        {
            return obj.DisplayName ?? obj.Name;
        }

        if (location.terrainFeatures.TryGetValue(tile, out var feature) && feature != null)
        {
            return feature.GetType().Name;
        }

        // Check buildings (all locations can have buildings in newer SDV versions)
        foreach (var building in location.buildings)
        {
            if (building.occupiesTile(tile))
            {
                return building.buildingType.Value ?? building.GetType().Name;
            }
        }

        if (location.isWaterTile(x, y))
        {
            return "water";
        }

        return "wall";
    }

    private PlayerState ReadPlayerState()
    {
        var player = Game1.player;
        var tool = player.CurrentTool;

        // Find watering can water level
        int waterLeft = 0;
        int waterMax = 40;
        foreach (var item in player.Items)
        {
            if (item is StardewValley.Tools.WateringCan wateringCan)
            {
                waterLeft = wateringCan.WaterLeft;
                waterMax = wateringCan.waterCanMax;
                break;
            }
        }

        return new PlayerState
        {
            Name = player.Name,
            TileX = player.TilePoint.X,
            TileY = player.TilePoint.Y,
            PixelX = (int)player.Position.X,
            PixelY = (int)player.Position.Y,
            FacingDirection = player.FacingDirection,
            Energy = (int)player.Stamina,
            MaxEnergy = player.MaxStamina,
            Health = player.health,
            MaxHealth = player.maxHealth,
            Money = player.Money,
            CurrentTool = tool?.DisplayName ?? "None",
            CurrentToolIndex = player.CurrentToolIndex,
            IsMoving = player.isMoving(),
            CanMove = player.CanMove,
            WateringCanWater = waterLeft,
            WateringCanMax = waterMax
        };
    }

    private TimeState ReadTimeState()
    {
        int timeOfDay = Game1.timeOfDay;
        int hour = timeOfDay / 100;
        int minute = timeOfDay % 100;

        string ampm = hour < 12 || hour >= 24 ? "AM" : "PM";
        int displayHour = hour % 12;
        if (displayHour == 0) displayHour = 12;

        return new TimeState
        {
            Hour = hour,
            Minute = minute,
            TimeString = $"{displayHour}:{minute:D2} {ampm}",
            Season = Game1.currentSeason,
            Day = Game1.dayOfMonth,
            Year = Game1.year,
            DayOfWeek = Game1.shortDayNameFromDayOfSeason(Game1.dayOfMonth),
            Weather = GetWeatherString()
        };
    }

    private string GetWeatherString()
    {
        if (Game1.isSnowing) return "snowy";
        if (Game1.isLightning) return "stormy";
        if (Game1.isRaining) return "rainy";
        return "sunny";
    }

    private LocationState ReadLocationState()
    {
        var player = Game1.player;
        var location = player.currentLocation;
        if (location == null) return null;

        var state = new LocationState
        {
            Name = location.Name,
            DisplayName = location.DisplayName ?? location.Name,
            IsOutdoors = location.IsOutdoors,
            IsFarm = location.IsFarm,
            MapWidth = location.Map?.Layers[0]?.LayerWidth ?? 0,
            MapHeight = location.Map?.Layers[0]?.LayerHeight ?? 0
        };

        // Read objects (within 15 tiles of player for performance)
        var playerTile = player.TilePoint;
        foreach (var pair in location.objects.Pairs)
        {
            var pos = pair.Key;
            if (Math.Abs(pos.X - playerTile.X) <= 15 && Math.Abs(pos.Y - playerTile.Y) <= 15)
            {
                var obj = pair.Value;
                state.Objects.Add(new TileObject
                {
                    X = (int)pos.X,
                    Y = (int)pos.Y,
                    Name = obj.DisplayName ?? obj.Name,
                    Type = obj.Type,
                    IsPassable = obj.isPassable()
                });
            }
        }

        // Read NPCs
        foreach (var npc in location.characters)
        {
            state.Npcs.Add(new NpcInfo
            {
                Name = npc.Name,
                TileX = npc.TilePoint.X,
                TileY = npc.TilePoint.Y,
                IsVillager = npc.IsVillager,
                Friendship = player.getFriendshipHeartLevelForNPC(npc.Name) * 250
            });
        }

        // Read crops (within 15 tiles)
        foreach (var pair in location.terrainFeatures.Pairs)
        {
            if (pair.Value is HoeDirt dirt && dirt.crop != null)
            {
                var pos = pair.Key;
                if (Math.Abs(pos.X - playerTile.X) <= 15 && Math.Abs(pos.Y - playerTile.Y) <= 15)
                {
                    var crop = dirt.crop;
                    state.Crops.Add(new CropInfo
                    {
                        X = (int)pos.X,
                        Y = (int)pos.Y,
                        CropName = GetCropName(crop),
                        DaysUntilHarvest = crop.dayOfCurrentPhase.Value,
                        IsWatered = dirt.state.Value == HoeDirt.watered,
                        IsReadyForHarvest = crop.fullyGrown.Value
                    });
                }
            }
        }

        return state;
    }

    private string GetCropName(Crop crop)
    {
        try
        {
            // Get crop name from its harvest item
            var item = ItemRegistry.Create(crop.indexOfHarvest.Value);
            return item?.DisplayName ?? $"Crop_{crop.indexOfHarvest.Value}";
        }
        catch
        {
            return $"Crop_{crop.indexOfHarvest.Value}";
        }
    }

    private List<InventoryItem> ReadInventory()
    {
        var player = Game1.player;
        var items = new List<InventoryItem>();
        var inventory = player.Items;

        for (int i = 0; i < Math.Min(inventory.Count, 36); i++)
        {
            var item = inventory[i];
            if (item != null)
            {
                items.Add(new InventoryItem
                {
                    Slot = i,
                    Name = item.DisplayName,
                    Type = GetItemType(item),
                    Stack = item.Stack,
                    Quality = item is StardewValley.Object obj ? obj.Quality : 0
                });
            }
        }

        return items;
    }

    private string GetItemType(Item item)
    {
        if (item is Tool) return "tool";
        if (item is StardewValley.Object obj)
        {
            if (obj.Category == StardewValley.Object.SeedsCategory) return "seed";
            if (obj.Category == StardewValley.Object.VegetableCategory) return "crop";
            if (obj.Category == StardewValley.Object.FruitsCategory) return "fruit";
        }
        return "object";
    }
}
