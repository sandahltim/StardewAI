using System.Linq;
using Microsoft.Xna.Framework;
using StardewAI.GameBridge.Models;
using StardewAI.GameBridge.Pathfinding;
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
            Landmarks = ReadLandmarks(),
            Inventory = ReadInventory(),
            // UI state for popup detection
            Menu = Game1.activeClickableMenu?.GetType().Name,
            Event = Game1.eventUp && Game1.currentLocation?.currentEvent != null
                ? Game1.currentLocation.currentEvent.id
                : null,
            DialogueUp = Game1.dialogueUp,
            Paused = Game1.paused
        };
    }

    /// <summary>
    /// Read Farm state regardless of player's current location.
    /// Used for morning planning when player is in FarmHouse.
    /// </summary>
    public FarmState ReadFarmState()
    {
        if (!Context.IsWorldReady)
            return null;

        var farm = Game1.getFarm();
        if (farm == null)
            return null;

        var state = new FarmState
        {
            Name = farm.Name,
            MapWidth = farm.Map?.Layers[0]?.LayerWidth ?? 0,
            MapHeight = farm.Map?.Layers[0]?.LayerHeight ?? 0,
            ShippingBin = new TilePosition { X = 71, Y = 14 }
        };

        // Read ALL crops on farm (no distance limit)
        foreach (var pair in farm.terrainFeatures.Pairs)
        {
            if (pair.Value is HoeDirt dirt && dirt.crop != null)
            {
                var pos = pair.Key;
                var crop = dirt.crop;

                // Calculate actual days until harvest
                int daysRemaining = 0;
                if (!crop.fullyGrown.Value)
                {
                    var phases = crop.phaseDays;
                    int currentPhase = crop.currentPhase.Value;
                    int dayInPhase = crop.dayOfCurrentPhase.Value;

                    if (currentPhase < phases.Count)
                    {
                        daysRemaining = Math.Max(0, phases[currentPhase] - dayInPhase);
                    }

                    for (int i = currentPhase + 1; i < phases.Count - 1; i++)
                    {
                        daysRemaining += phases[i];
                    }
                }

                state.Crops.Add(new CropInfo
                {
                    X = (int)pos.X,
                    Y = (int)pos.Y,
                    CropName = GetCropName(crop),
                    DaysUntilHarvest = daysRemaining,
                    IsWatered = dirt.state.Value == HoeDirt.watered,
                    IsReadyForHarvest = crop.currentPhase.Value >= crop.phaseDays.Count - 1
                });
            }
        }

        // Read debris/objects on farm (for clearing tasks)
        foreach (var pair in farm.objects.Pairs)
        {
            var pos = pair.Key;
            var obj = pair.Value;

            state.Objects.Add(new TileObject
            {
                X = (int)pos.X,
                Y = (int)pos.Y,
                Name = obj.DisplayName ?? obj.Name,
                Type = obj.Type,
                IsPassable = obj.isPassable(),
                IsForageable = obj.isForage(),
                CanInteract = false,
                InteractionType = null
            });
        }

        // Count tilled empty tiles (for planting) and grass positions
        foreach (var pair in farm.terrainFeatures.Pairs)
        {
            if (pair.Value is HoeDirt dirt && dirt.crop == null)
            {
                state.TilledTiles.Add(new TilePosition
                {
                    X = (int)pair.Key.X,
                    Y = (int)pair.Key.Y
                });
            }
            else if (pair.Value is Grass)
            {
                // Grass needs to be cleared before tilling
                state.GrassPositions.Add(new TilePosition
                {
                    X = (int)pair.Key.X,
                    Y = (int)pair.Key.Y
                });
            }
        }

        // Read Chests on farm for inventory management
        foreach (var pair in farm.objects.Pairs)
        {
            if (pair.Value is StardewValley.Objects.Chest chest)
            {
                var pos = pair.Key;
                var items = chest.Items.Where(i => i != null).ToList();
                
                var chestInfo = new ChestInfo
                {
                    X = (int)pos.X,
                    Y = (int)pos.Y,
                    Name = string.IsNullOrEmpty(chest.DisplayName) ? "Chest" : chest.DisplayName,
                    ItemCount = items.Sum(i => i.Stack),
                    SlotsFree = chest.GetActualCapacity() - items.Count
                };
                
                // Group items by name for summary
                var grouped = items
                    .GroupBy(i => i.DisplayName)
                    .Select(g => new ChestItemSummary
                    {
                        ItemName = g.Key,
                        Quantity = g.Sum(i => i.Stack),
                        Category = GetItemCategory(g.First())
                    })
                    .ToList();
                
                chestInfo.Contents = grouped;
                state.Chests.Add(chestInfo);
            }
        }

        // Read ResourceClumps (large stumps, logs, boulders that need tool upgrades)
        foreach (var clump in farm.resourceClumps)
        {
            // ResourceClump types: 600=Stump, 602=Log, 622=Meteorite, 672=Boulder, 752=Copper, 754=Iron, 756=Gold, 758=Iridium
            string type = clump.parentSheetIndex.Value switch
            {
                600 => "Stump",
                602 => "Log",
                622 => "Meteorite",
                672 => "Boulder",
                752 => "Copper Node",
                754 => "Iron Node",
                756 => "Gold Node",
                758 => "Iridium Node",
                _ => $"Clump_{clump.parentSheetIndex.Value}"
            };

            string requiredTool = clump.parentSheetIndex.Value switch
            {
                600 => "Copper Axe",       // Stump needs copper axe
                602 => "Steel Axe",        // Log needs steel axe
                622 => "Gold Pickaxe",     // Meteorite needs gold pickaxe
                672 => "Steel Pickaxe",    // Boulder needs steel pickaxe
                _ => "Pickaxe"
            };

            state.ResourceClumps.Add(new ResourceClumpInfo
            {
                X = (int)clump.Tile.X,
                Y = (int)clump.Tile.Y,
                Width = clump.width.Value,
                Height = clump.height.Value,
                Type = type,
                RequiredTool = requiredTool,
                Health = (int)clump.health.Value
            });
        }

        return state;
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
            // Use cardinal directions (north/south/east/west) for clarity
            // north = screen up, south = screen down, east = screen right, west = screen left
            Directions = new Dictionary<string, DirectionInfo>
            {
                ["north"] = ScanDirection(location, start.X, start.Y, 0, -1, maxTiles, mapWidth, mapHeight),
                ["south"] = ScanDirection(location, start.X, start.Y, 0, 1, maxTiles, mapWidth, mapHeight),
                ["west"] = ScanDirection(location, start.X, start.Y, -1, 0, maxTiles, mapWidth, mapHeight),
                ["east"] = ScanDirection(location, start.X, start.Y, 1, 0, maxTiles, mapWidth, mapHeight)
            },
            NearestWater = FindNearestWater(location, start.X, start.Y, 25)
        };
    }

    /// <summary>Find nearest water tile for refilling watering can</summary>
    private WaterSourceInfo FindNearestWater(GameLocation location, int playerX, int playerY, int maxDistance)
    {
        // Spiral outward from player to find nearest water
        for (int dist = 1; dist <= maxDistance; dist++)
        {
            // Check tiles at this distance (square perimeter)
            for (int dx = -dist; dx <= dist; dx++)
            {
                for (int dy = -dist; dy <= dist; dy++)
                {
                    // Only check perimeter tiles (not interior)
                    if (Math.Abs(dx) != dist && Math.Abs(dy) != dist) continue;

                    int x = playerX + dx;
                    int y = playerY + dy;

                    if (location.isWaterTile(x, y))
                    {
                        // Determine general direction
                        string direction = "here";
                        if (Math.Abs(dy) > Math.Abs(dx))
                            direction = dy < 0 ? "north" : "south";
                        else if (Math.Abs(dx) > Math.Abs(dy))
                            direction = dx < 0 ? "west" : "east";
                        else if (dx != 0 || dy != 0)
                            direction = (dy < 0 ? "north" : "south") + (dx < 0 ? "west" : "east");

                        return new WaterSourceInfo
                        {
                            X = x,
                            Y = y,
                            Distance = Math.Abs(dx) + Math.Abs(dy),
                            Direction = direction
                        };
                    }
                }
            }
        }

        return null; // No water found within range
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

        // Check if tillable - use actual game property, not blanket Farm check
        // Tiles need "Diggable" property AND be passable (not porch, paths, etc.)
        bool hasDiggable = location.doesTileHaveProperty(x, y, "Diggable", "Back") != null;
        bool isPassable = location.isTilePassable(new xTile.Dimensions.Location(x, y), Game1.viewport);

        result.CanTill = hasDiggable && isPassable;
        result.State = result.CanTill ? "clear" : "blocked";

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
        AdjacentTileInfo adjacentTile = null;

        for (int i = 1; i <= maxTiles; i++)
        {
            int x = startX + dx * i;
            int y = startY + dy * i;

            if (x < 0 || y < 0 || x >= mapWidth || y >= mapHeight)
            {
                blocker = "map_edge";
                break;
            }

            // Get detailed tile state for immediately adjacent tile (i=1)
            if (i == 1)
            {
                adjacentTile = GetAdjacentTileInfo(location, x, y);
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
            Blocker = blocker,
            AdjacentTile = adjacentTile
        };
    }

    /// <summary>Get detailed tile state for phantom failure detection</summary>
    private AdjacentTileInfo GetAdjacentTileInfo(GameLocation location, int x, int y)
    {
        var tileVec = new Vector2(x, y);
        var info = new AdjacentTileInfo
        {
            X = x,
            Y = y,
            IsTilled = false,
            HasCrop = false,
            IsWatered = false,
            CanTill = false,
            CanPlant = false,
            BlockerType = null
        };

        // Check for objects blocking the tile (stone, weeds, etc.)
        if (location.Objects.TryGetValue(tileVec, out var obj))
        {
            info.BlockerType = obj.Name;
            return info;
        }

        // Check terrain features (HoeDirt for farming)
        if (location.terrainFeatures.TryGetValue(tileVec, out var feature))
        {
            if (feature is StardewValley.TerrainFeatures.HoeDirt hoeDirt)
            {
                info.IsTilled = true;
                info.HasCrop = hoeDirt.crop != null;
                info.IsWatered = hoeDirt.state.Value == 1;
                info.CanPlant = hoeDirt.crop == null;  // Can plant if tilled but no crop
            }
            else if (feature is StardewValley.TerrainFeatures.Tree)
            {
                info.BlockerType = "Tree";
            }
            else if (feature is StardewValley.TerrainFeatures.Grass)
            {
                info.BlockerType = "Grass";
            }
            else if (!feature.isPassable())
            {
                info.BlockerType = feature.GetType().Name;
            }
            return info;
        }

        // Empty tile - check if it can be tilled (on farm, diggable)
        if (location is Farm || location.Name == "Farm")
        {
            // Simple check: if no obstruction and we're on farm, likely tillable
            var tileLocation = new xTile.Dimensions.Location(x, y);
            info.CanTill = location.isTilePassable(tileLocation, Game1.viewport) &&
                          !location.isWaterTile(x, y);
        }

        return info;
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

        // Check for ResourceClumps (large stumps, logs, boulders)
        foreach (var clump in location.resourceClumps)
        {
            if (x >= clump.Tile.X && x < clump.Tile.X + clump.width.Value &&
                y >= clump.Tile.Y && y < clump.Tile.Y + clump.height.Value)
            {
                return clump.parentSheetIndex.Value switch
                {
                    600 => "Stump",
                    602 => "Log",
                    622 => "Meteorite",
                    672 => "Boulder",
                    _ => "ResourceClump"
                };
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

        // Get currently selected item (works for both tools AND objects like seeds)
        var selectedIndex = player.CurrentToolIndex;
        var selectedItem = (selectedIndex >= 0 && selectedIndex < player.Items.Count)
            ? player.Items[selectedIndex]
            : null;
        string selectedItemName = selectedItem?.DisplayName ?? "None";

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
            Facing = TilePathfinder.FacingToCardinal(player.FacingDirection),
            Energy = (int)player.Stamina,
            MaxEnergy = player.MaxStamina,
            Health = player.health,
            MaxHealth = player.maxHealth,
            Money = player.Money,
            CurrentTool = selectedItemName,
            CurrentToolIndex = selectedIndex,
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

        // Find shipping bin on Farm (standard farm location is around 71,14)
        if (location is StardewValley.Farm farm)
        {
            // Standard farm shipping bin location
            state.ShippingBin = new TilePosition { X = 71, Y = 14 };
        }

        // Read objects (within 15 tiles of player for performance)
        var playerTile = player.TilePoint;
        foreach (var pair in location.objects.Pairs)
        {
            var pos = pair.Key;
            if (Math.Abs(pos.X - playerTile.X) <= 15 && Math.Abs(pos.Y - playerTile.Y) <= 15)
            {
                var obj = pair.Value;

                // Determine if forageable (can be picked up)
                bool isForageable = obj.isForage() ||
                    obj.Category == StardewValley.Object.GreensCategory ||
                    obj.Category == StardewValley.Object.flowersCategory;

                // Determine interaction type
                string interactionType = null;
                bool canInteract = false;
                if (obj is StardewValley.Objects.Chest)
                {
                    canInteract = true;
                    interactionType = "chest";
                }
                else if (obj.bigCraftable.Value && obj.MinutesUntilReady > 0)
                {
                    canInteract = true;
                    interactionType = "machine";
                }
                else if (obj.bigCraftable.Value)
                {
                    canInteract = true;
                    interactionType = "craftable";
                }

                state.Objects.Add(new TileObject
                {
                    X = (int)pos.X,
                    Y = (int)pos.Y,
                    Name = obj.DisplayName ?? obj.Name,
                    Type = obj.Type,
                    IsPassable = obj.isPassable(),
                    IsForageable = isForageable,
                    CanInteract = canInteract,
                    InteractionType = interactionType
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

                    // Calculate actual days until harvest
                    int daysRemaining = 0;
                    if (!crop.fullyGrown.Value)
                    {
                        var phases = crop.phaseDays;
                        int currentPhase = crop.currentPhase.Value;
                        int dayInPhase = crop.dayOfCurrentPhase.Value;

                        // Days remaining in current phase
                        if (currentPhase < phases.Count)
                        {
                            daysRemaining = Math.Max(0, phases[currentPhase] - dayInPhase);
                        }

                        // Add days for all remaining phases (except the last 99999 "done" phase)
                        for (int i = currentPhase + 1; i < phases.Count - 1; i++)
                        {
                            daysRemaining += phases[i];
                        }
                    }

                    state.Crops.Add(new CropInfo
                    {
                        X = (int)pos.X,
                        Y = (int)pos.Y,
                        CropName = GetCropName(crop),
                        DaysUntilHarvest = daysRemaining,
                        IsWatered = dirt.state.Value == HoeDirt.watered,
                        IsReadyForHarvest = crop.currentPhase.Value >= crop.phaseDays.Count - 1
                    });
                }
            }
        }

        return state;
    }

    private Dictionary<string, LandmarkInfo> ReadLandmarks()
    {
        var landmarks = new Dictionary<string, LandmarkInfo>();
        var player = Game1.player;
        var location = player.currentLocation;
        if (location == null) return landmarks;

        var playerX = player.TilePoint.X;
        var playerY = player.TilePoint.Y;

        if (location is StardewValley.Farm)
        {
            var farmhouse = BuildLandmarkInfo(64, 15, playerX, playerY);
            if (farmhouse != null)
                landmarks["farmhouse"] = farmhouse;

            var shippingBin = BuildLandmarkInfo(71, 14, playerX, playerY);
            if (shippingBin != null)
                landmarks["shipping_bin"] = shippingBin;
        }

        var nearestWater = FindNearestWater(location, playerX, playerY, 25);
        if (nearestWater != null)
        {
            landmarks["water"] = new LandmarkInfo
            {
                Distance = nearestWater.Distance,
                Direction = nearestWater.Direction
            };
        }

        return landmarks;
    }

    private LandmarkInfo BuildLandmarkInfo(int targetX, int targetY, int playerX, int playerY)
    {
        int dx = targetX - playerX;
        int dy = targetY - playerY;
        int distance = Math.Abs(dx) + Math.Abs(dy);

        string direction;
        if (dx == 0 && dy == 0)
        {
            direction = "here";
        }
        else
        {
            string northSouth = dy < 0 ? "north" : dy > 0 ? "south" : "";
            string eastWest = dx < 0 ? "west" : dx > 0 ? "east" : "";
            direction = $"{northSouth}{eastWest}";
        }

        return new LandmarkInfo
        {
            Distance = distance,
            Direction = direction
        };
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

    private string GetItemCategory(Item item)
    {
        if (item is Tool) return "tool";
        if (item is StardewValley.Object obj)
        {
            // Category values from Stardew Valley source
            return obj.Category switch
            {
                -74 => "seed",      // SeedsCategory
                -75 => "crop",      // VegetableCategory  
                -79 => "fruit",     // FruitsCategory
                -4 => "fish",       // FishCategory
                -7 => "cooking",    // CookingCategory (cooked dishes)
                -2 => "gem",        // GemCategory
                -12 => "mineral",   // MineralsCategory
                -15 => "ore",       // MetalResources
                -16 => "material",  // BuildingResources (wood, stone)
                -19 => "fertilizer",// FertilizerCategory
                -80 => "flower",    // FlowersCategory
                -81 => "forage",    // GreensCategory
                -26 => "artisan",   // ArtisanGoodsCategory
                -27 => "syrup",     // SyrupCategory
                -28 => "monster_loot", // MonsterLootCategory
                -8 => "crafting",   // CraftingCategory
                _ => "misc"
            };
        }
        return "object";
    }
}
