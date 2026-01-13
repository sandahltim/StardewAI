using Microsoft.Xna.Framework;
using StardewAI.GameBridge.Models;
using StardewAI.GameBridge.Pathfinding;
using StardewModdingAPI;
using StardewModdingAPI.Events;
using StardewValley;
using StardewValley.Buildings;
using StardewValley.Locations;
using StardewValley.Objects;
using System.Collections.Concurrent;

namespace StardewAI.GameBridge;

/// <summary>
/// SMAPI mod entry point. Provides HTTP API for AI agent control.
///
/// Thread Safety:
/// - HTTP server runs on background thread
/// - Game state is read and actions executed on main thread via UpdateTicked
/// - ConcurrentQueue bridges the two threads
/// </summary>
public class ModEntry : Mod
{
    private HttpServer _httpServer;
    private GameStateReader _stateReader;
    private ActionExecutor _actionExecutor;
    private TilePathfinder _pathfinder;
    private volatile SurroundingsState _cachedSurroundings;
    private volatile FarmState _cachedFarmState;
    private volatile SkillsState _cachedSkills;

    // Thread-safe queues for cross-thread communication
    private readonly ConcurrentQueue<(ActionCommand Command, Action<ActionResult> Callback)> _actionQueue = new();

    // Cached state (updated on game thread, read by HTTP thread)
    private volatile GameState _cachedState;

    // Config - port 8790 (8765/8766 reserved, 8780 is llama-server)
    private const int HttpPort = 8790;
    private const int StateUpdateInterval = 15; // Every 15 ticks (4x per second at 60fps)

    public override void Entry(IModHelper helper)
    {
        // Initialize components
        _stateReader = new GameStateReader(Monitor);
        _actionExecutor = new ActionExecutor(Monitor);
        _pathfinder = new TilePathfinder();

        // Start HTTP server
        _httpServer = new HttpServer(HttpPort, Monitor);
        _httpServer.GetGameState = () => _cachedState;
        _httpServer.GetSurroundings = () => _cachedSurroundings;
        _httpServer.GetFarmState = () => _cachedFarmState;
        _httpServer.QueueAction = QueueActionFromHttp;

        // Pathfinding & navigation callbacks
        _httpServer.CheckPath = CheckPathFromHttp;
        _httpServer.CheckPassable = CheckPassableFromHttp;
        _httpServer.CheckPassableArea = CheckPassableAreaFromHttp;
        _httpServer.GetSkills = () => _cachedSkills;

        // Game world data callbacks
        _httpServer.GetNpcs = ReadNpcsState;
        _httpServer.GetAnimals = ReadAnimalsState;
        _httpServer.GetMachines = ReadMachinesState;
        _httpServer.GetCalendar = ReadCalendarState;
        _httpServer.GetFishing = ReadFishingState;
        _httpServer.GetMining = ReadMiningState;
        _httpServer.GetStorage = ReadStorageState;

        _httpServer.Start();

        // Subscribe to events
        helper.Events.GameLoop.UpdateTicked += OnUpdateTicked;
        helper.Events.GameLoop.SaveLoaded += OnSaveLoaded;
        helper.Events.GameLoop.ReturnedToTitle += OnReturnedToTitle;
        helper.Events.GameLoop.GameLaunched += OnGameLaunched;

        Monitor.Log($"StardewAI GameBridge loaded - HTTP API on port {HttpPort}", LogLevel.Info);
    }

    private void OnGameLaunched(object sender, GameLaunchedEventArgs e)
    {
        Monitor.Log("GameBridge ready for connections", LogLevel.Info);
    }

    private void OnSaveLoaded(object sender, SaveLoadedEventArgs e)
    {
        Monitor.Log($"Save loaded: {Game1.player.Name} on {Game1.player.farmName}", LogLevel.Info);
        _actionExecutor.Reset();
    }

    private void OnReturnedToTitle(object sender, ReturnedToTitleEventArgs e)
    {
        Monitor.Log("Returned to title - clearing state", LogLevel.Debug);
        _cachedState = null;
        _actionExecutor.Reset();
    }

    private void OnUpdateTicked(object sender, UpdateTickedEventArgs e)
    {
        // Update action executor EVERY tick for smooth movement
        _actionExecutor.Update();

        // Update cached game state periodically
        if (e.IsMultipleOf(StateUpdateInterval))
        {
            try
            {
                _cachedState = _stateReader.ReadState();
                _cachedSurroundings = _stateReader.ReadSurroundings();
                _cachedFarmState = _stateReader.ReadFarmState();
                _cachedSkills = ReadSkillsState();
            }
            catch (Exception ex)
            {
                Monitor.Log($"Error reading game state: {ex.Message}", LogLevel.Error);
            }
        }

        // Process queued actions from HTTP thread
        while (_actionQueue.TryDequeue(out var item))
        {
            try
            {
                var result = _actionExecutor.QueueAction(item.Command);
                item.Callback?.Invoke(result);
            }
            catch (Exception ex)
            {
                Monitor.Log($"Error executing action: {ex.Message}", LogLevel.Error);
                item.Callback?.Invoke(new ActionResult
                {
                    Success = false,
                    Error = ex.Message,
                    State = ActionState.Failed
                });
            }
        }

        // Continue any multi-frame actions
        _actionExecutor.Update();
    }

    /// <summary>
    /// Called from HTTP thread - queues action for main thread execution.
    /// Uses blocking wait to return result synchronously to HTTP caller.
    /// </summary>
    private ActionResult QueueActionFromHttp(ActionCommand command)
    {
        // For quick actions, we use a synchronization primitive to wait for result
        var resultReady = new ManualResetEventSlim(false);
        ActionResult result = null;

        _actionQueue.Enqueue((command, r =>
        {
            result = r;
            resultReady.Set();
        }));

        // Wait for result (timeout after 5 seconds)
        if (resultReady.Wait(5000))
        {
            return result;
        }

        return new ActionResult
        {
            Success = false,
            Error = "Action timed out",
            State = ActionState.Failed
        };
    }

    /// <summary>Check if a path exists between two points</summary>
    private PathCheckResult CheckPathFromHttp(int startX, int startY, int endX, int endY)
    {
        if (!Context.IsWorldReady || Game1.currentLocation == null)
        {
            return new PathCheckResult { Reachable = false, PathLength = 0, Path = null };
        }

        var path = _pathfinder.FindPath(
            new Point(startX, startY),
            new Point(endX, endY),
            Game1.currentLocation
        );

        if (path == null || path.Count == 0)
        {
            return new PathCheckResult { Reachable = false, PathLength = 0, Path = null };
        }

        return new PathCheckResult
        {
            Reachable = true,
            PathLength = path.Count,
            Path = path.Select(p => new TilePosition { X = p.X, Y = p.Y }).ToList()
        };
    }

    /// <summary>Check if a single tile is passable</summary>
    private PassableResult CheckPassableFromHttp(int x, int y)
    {
        if (!Context.IsWorldReady || Game1.currentLocation == null)
        {
            return new PassableResult { X = x, Y = y, Passable = false, Blocker = "not_in_game" };
        }

        bool passable = _pathfinder.IsTilePassable(new Point(x, y), Game1.currentLocation);

        string blocker = null;
        if (!passable)
        {
            blocker = GetBlockerName(Game1.currentLocation, x, y);
        }

        return new PassableResult { X = x, Y = y, Passable = passable, Blocker = blocker };
    }

    /// <summary>Check passability for an area around a center point</summary>
    private PassableAreaResult CheckPassableAreaFromHttp(int centerX, int centerY, int radius)
    {
        var result = new PassableAreaResult
        {
            CenterX = centerX,
            CenterY = centerY,
            Radius = radius,
            Tiles = new List<PassableResult>()
        };

        if (!Context.IsWorldReady || Game1.currentLocation == null)
        {
            return result;
        }

        var location = Game1.currentLocation;

        for (int dy = -radius; dy <= radius; dy++)
        {
            for (int dx = -radius; dx <= radius; dx++)
            {
                int x = centerX + dx;
                int y = centerY + dy;

                bool passable = _pathfinder.IsTilePassable(new Point(x, y), location);
                string blocker = passable ? null : GetBlockerName(location, x, y);

                result.Tiles.Add(new PassableResult
                {
                    X = x,
                    Y = y,
                    Passable = passable,
                    Blocker = blocker
                });
            }
        }

        return result;
    }

    /// <summary>Get the name of what's blocking a tile</summary>
    private string GetBlockerName(GameLocation location, int x, int y)
    {
        var tile = new Vector2(x, y);

        // Check for objects
        if (location.objects.TryGetValue(tile, out var obj))
        {
            return obj.DisplayName ?? obj.Name ?? "object";
        }

        // Check for terrain features
        if (location.terrainFeatures.TryGetValue(tile, out var feature))
        {
            return feature.GetType().Name;
        }

        // Check for buildings
        foreach (var building in location.buildings)
        {
            if (building.occupiesTile(tile))
            {
                return building.buildingType.Value ?? "building";
            }
        }

        // Check for water
        if (location.isWaterTile(x, y))
        {
            return "water";
        }

        // Check map boundaries
        var layer = location.Map?.GetLayer("Back");
        if (layer != null && (x < 0 || y < 0 || x >= layer.LayerWidth || y >= layer.LayerHeight))
        {
            return "map_edge";
        }

        // Generic wall/cliff
        return "wall";
    }

    /// <summary>Read player skill levels</summary>
    private SkillsState ReadSkillsState()
    {
        if (!Context.IsWorldReady || Game1.player == null)
            return null;

        var player = Game1.player;

        return new SkillsState
        {
            Farming = new SkillInfo
            {
                Level = player.FarmingLevel,
                Xp = player.experiencePoints[0],
                XpToNextLevel = GetXpForLevel(player.FarmingLevel + 1) - player.experiencePoints[0],
                Profession5 = GetFarmingProfession5(player),
                Profession10 = GetFarmingProfession10(player)
            },
            Fishing = new SkillInfo
            {
                Level = player.FishingLevel,
                Xp = player.experiencePoints[1],
                XpToNextLevel = GetXpForLevel(player.FishingLevel + 1) - player.experiencePoints[1],
                Profession5 = GetFishingProfession5(player),
                Profession10 = GetFishingProfession10(player)
            },
            Foraging = new SkillInfo
            {
                Level = player.ForagingLevel,
                Xp = player.experiencePoints[2],
                XpToNextLevel = GetXpForLevel(player.ForagingLevel + 1) - player.experiencePoints[2],
                Profession5 = GetForagingProfession5(player),
                Profession10 = GetForagingProfession10(player)
            },
            Mining = new SkillInfo
            {
                Level = player.MiningLevel,
                Xp = player.experiencePoints[3],
                XpToNextLevel = GetXpForLevel(player.MiningLevel + 1) - player.experiencePoints[3],
                Profession5 = GetMiningProfession5(player),
                Profession10 = GetMiningProfession10(player)
            },
            Combat = new SkillInfo
            {
                Level = player.CombatLevel,
                Xp = player.experiencePoints[4],
                XpToNextLevel = GetXpForLevel(player.CombatLevel + 1) - player.experiencePoints[4],
                Profession5 = GetCombatProfession5(player),
                Profession10 = GetCombatProfession10(player)
            },
            Luck = new SkillInfo
            {
                Level = player.LuckLevel,
                Xp = 0,
                XpToNextLevel = 0,
                Profession5 = null,
                Profession10 = null
            }
        };
    }

    private static int GetXpForLevel(int level) => level switch
    {
        1 => 100, 2 => 380, 3 => 770, 4 => 1300, 5 => 2150,
        6 => 3300, 7 => 4800, 8 => 6900, 9 => 10000, 10 => 15000,
        _ => level > 10 ? 15000 : 0
    };

    // Profession helpers (IDs from game data)
    private static string GetFarmingProfession5(Farmer p) =>
        p.professions.Contains(0) ? "Rancher" : p.professions.Contains(1) ? "Tiller" : null;
    private static string GetFarmingProfession10(Farmer p) =>
        p.professions.Contains(2) ? "Coopmaster" : p.professions.Contains(3) ? "Shepherd" :
        p.professions.Contains(4) ? "Artisan" : p.professions.Contains(5) ? "Agriculturist" : null;

    private static string GetFishingProfession5(Farmer p) =>
        p.professions.Contains(6) ? "Fisher" : p.professions.Contains(7) ? "Trapper" : null;
    private static string GetFishingProfession10(Farmer p) =>
        p.professions.Contains(8) ? "Angler" : p.professions.Contains(9) ? "Pirate" :
        p.professions.Contains(10) ? "Mariner" : p.professions.Contains(11) ? "Luremaster" : null;

    private static string GetForagingProfession5(Farmer p) =>
        p.professions.Contains(12) ? "Forester" : p.professions.Contains(13) ? "Gatherer" : null;
    private static string GetForagingProfession10(Farmer p) =>
        p.professions.Contains(14) ? "Lumberjack" : p.professions.Contains(15) ? "Tapper" :
        p.professions.Contains(16) ? "Botanist" : p.professions.Contains(17) ? "Tracker" : null;

    private static string GetMiningProfession5(Farmer p) =>
        p.professions.Contains(18) ? "Miner" : p.professions.Contains(19) ? "Geologist" : null;
    private static string GetMiningProfession10(Farmer p) =>
        p.professions.Contains(20) ? "Blacksmith" : p.professions.Contains(21) ? "Prospector" :
        p.professions.Contains(22) ? "Excavator" : p.professions.Contains(23) ? "Gemologist" : null;

    private static string GetCombatProfession5(Farmer p) =>
        p.professions.Contains(24) ? "Fighter" : p.professions.Contains(25) ? "Scout" : null;
    private static string GetCombatProfession10(Farmer p) =>
        p.professions.Contains(26) ? "Brute" : p.professions.Contains(27) ? "Defender" :
        p.professions.Contains(28) ? "Acrobat" : p.professions.Contains(29) ? "Desperado" : null;

    // ============================================
    // NPC DATA READER
    // ============================================

    private NpcsState ReadNpcsState()
    {
        var result = new NpcsState();
        if (!Context.IsWorldReady) return result;

        var player = Game1.player;

        foreach (var npc in Utility.getAllCharacters())
        {
            if (npc == null) continue;

            var friendship = player.friendshipData.TryGetValue(npc.Name, out var f) ? f : null;

            result.Npcs.Add(new NpcDetails
            {
                Name = npc.Name,
                DisplayName = npc.displayName ?? npc.Name,
                Location = npc.currentLocation?.Name ?? "Unknown",
                TileX = npc.TilePoint.X,
                TileY = npc.TilePoint.Y,
                IsVillager = npc.IsVillager,
                CanSocialize = npc.CanSocialize,
                FriendshipPoints = friendship?.Points ?? 0,
                FriendshipHearts = friendship?.Points / 250 ?? 0,
                CanDate = npc.datable.Value,
                IsDating = friendship?.IsDating() ?? false,
                IsMarried = friendship?.IsMarried() ?? false,
                BirthdaySeason = npc.Birthday_Season ?? "",
                BirthdayDay = npc.Birthday_Day,
                IsBirthdayToday = npc.isBirthday(),
                GiftedToday = friendship?.GiftsToday > 0,
                GiftsThisWeek = friendship?.GiftsThisWeek ?? 0
            });
        }

        return result;
    }

    // ============================================
    // ANIMAL DATA READER
    // ============================================

    private AnimalsState ReadAnimalsState()
    {
        var result = new AnimalsState();
        if (!Context.IsWorldReady) return result;

        var farm = Game1.getFarm();
        if (farm == null) return result;

        // Read animals
        foreach (var animal in farm.getAllFarmAnimals())
        {
            result.Animals.Add(new AnimalDetails
            {
                Id = animal.myID.Value,
                Name = animal.Name,
                Type = animal.type.Value,
                BuildingName = animal.home?.GetIndoorsName() ?? "Outside",
                TileX = animal.TilePoint.X,
                TileY = animal.TilePoint.Y,
                IsOutside = animal.currentLocation == farm,
                Happiness = animal.happiness.Value,
                Friendship = animal.friendshipTowardFarmer.Value,
                WasPetToday = animal.wasPet.Value,
                ProducedToday = animal.currentProduce.Value != null,
                CurrentProduct = animal.currentProduce.Value ?? "",
                Age = animal.age.Value
            });
        }

        // Read buildings
        foreach (var building in farm.buildings)
        {
            if (building.GetIndoors() is AnimalHouse animalHouse)
            {
                result.Buildings.Add(new BuildingDetails
                {
                    Type = building.buildingType.Value,
                    Name = building.GetIndoorsName() ?? building.buildingType.Value,
                    TileX = building.tileX.Value,
                    TileY = building.tileY.Value,
                    AnimalCount = animalHouse.animalsThatLiveHere.Count,
                    MaxAnimals = animalHouse.animalLimit.Value,
                    DoorOpen = building.animalDoorOpen.Value
                });
            }
        }

        return result;
    }

    // ============================================
    // MACHINE DATA READER
    // ============================================

    private MachinesState ReadMachinesState()
    {
        var result = new MachinesState();
        if (!Context.IsWorldReady) return result;

        // Check all locations for machines
        foreach (var location in Game1.locations)
        {
            ReadMachinesInLocation(location, result);

            // Check buildings in this location
            foreach (var building in location.buildings)
            {
                var indoors = building.GetIndoors();
                if (indoors != null)
                {
                    ReadMachinesInLocation(indoors, result);
                }
            }
        }

        return result;
    }

    private void ReadMachinesInLocation(GameLocation location, MachinesState result)
    {
        foreach (var pair in location.objects.Pairs)
        {
            var obj = pair.Value;

            // Check if it's a machine (BigCraftable that processes items)
            if (!obj.bigCraftable.Value) continue;

            // Common machine names
            var machineNames = new HashSet<string>
            {
                "Keg", "Preserves Jar", "Cheese Press", "Mayonnaise Machine",
                "Loom", "Oil Maker", "Seed Maker", "Crystalarium",
                "Recycling Machine", "Furnace", "Charcoal Kiln",
                "Cask", "Dehydrator", "Fish Smoker", "Bait Maker",
                "Bone Mill", "Geode Crusher", "Ostrich Incubator",
                "Slime Egg-Press", "Worm Bin", "Tapper", "Heavy Tapper",
                "Lightning Rod", "Bee House", "Mushroom Box"
            };

            if (!machineNames.Contains(obj.Name)) continue;

            var heldObject = obj.heldObject.Value;

            result.Machines.Add(new MachineDetails
            {
                Name = obj.Name,
                Location = location.Name,
                TileX = (int)pair.Key.X,
                TileY = (int)pair.Key.Y,
                IsProcessing = obj.MinutesUntilReady > 0,
                InputItem = heldObject?.Name,
                OutputItem = heldObject?.Name,
                MinutesUntilReady = obj.MinutesUntilReady,
                ReadyForHarvest = obj.readyForHarvest.Value,
                NeedsInput = !obj.readyForHarvest.Value && obj.MinutesUntilReady == 0
            });
        }
    }

    // ============================================
    // CALENDAR DATA READER
    // ============================================

    private CalendarState ReadCalendarState()
    {
        var result = new CalendarState
        {
            Season = Game1.currentSeason,
            Day = Game1.dayOfMonth,
            Year = Game1.year,
            DayOfWeek = Game1.shortDayNameFromDayOfSeason(Game1.dayOfMonth),
            DaysUntilSeasonEnd = 28 - Game1.dayOfMonth
        };

        // Check for today's event
        if (Utility.isFestivalDay())
        {
            result.TodayEvent = GetFestivalName(Game1.currentSeason, Game1.dayOfMonth);
        }

        // Upcoming events this season
        for (int day = Game1.dayOfMonth + 1; day <= 28; day++)
        {
            var festivalName = GetFestivalName(Game1.currentSeason, day);
            if (festivalName != null)
            {
                result.UpcomingEvents.Add(new CalendarEvent
                {
                    Day = day,
                    Season = Game1.currentSeason,
                    Name = festivalName,
                    Type = "festival"
                });
            }
        }

        // Upcoming birthdays
        foreach (var npc in Utility.getAllCharacters())
        {
            if (npc?.Birthday_Season == Game1.currentSeason && npc.Birthday_Day > Game1.dayOfMonth)
            {
                result.UpcomingBirthdays.Add(new CalendarEvent
                {
                    Day = npc.Birthday_Day,
                    Season = Game1.currentSeason,
                    Name = npc.displayName ?? npc.Name,
                    Type = "birthday"
                });
            }
        }

        // Sort by day
        result.UpcomingBirthdays.Sort((a, b) => a.Day.CompareTo(b.Day));

        return result;
    }

    private static string GetFestivalName(string season, int day)
    {
        return (season, day) switch
        {
            ("spring", 13) => "Egg Festival",
            ("spring", 24) => "Flower Dance",
            ("summer", 11) => "Luau",
            ("summer", 28) => "Dance of the Moonlight Jellies",
            ("fall", 16) => "Stardew Valley Fair",
            ("fall", 27) => "Spirit's Eve",
            ("winter", 8) => "Festival of Ice",
            ("winter", 25) => "Feast of the Winter Star",
            _ => null
        };
    }

    // ============================================
    // FISHING DATA READER
    // ============================================

    private FishingState ReadFishingState()
    {
        var result = new FishingState();
        if (!Context.IsWorldReady) return result;

        var location = Game1.currentLocation;
        result.Location = location?.Name ?? "Unknown";
        result.Weather = Game1.isRaining ? "Rainy" : "Sunny";
        result.Season = Game1.currentSeason;
        result.TimeOfDay = Game1.timeOfDay;

        // Note: Getting exact available fish requires complex game data lookup
        // This provides basic location info; full fish data would need Content API
        result.AvailableFish = new List<FishDetails>();

        return result;
    }

    // ============================================
    // MINING DATA READER
    // ============================================

    private MiningState ReadMiningState()
    {
        var result = new MiningState();
        if (!Context.IsWorldReady) return result;

        var location = Game1.currentLocation;
        result.Location = location?.Name ?? "Unknown";

        if (location is MineShaft mine)
        {
            result.Floor = mine.mineLevel;
            result.FloorType = GetMineFloorType(mine.mineLevel);
            result.LadderFound = mine.Objects.Values.Any(o => o.Name == "Ladder");
            result.ShaftFound = mine.Objects.Values.Any(o => o.Name == "Shaft");

            // Read rocks/ores
            foreach (var pair in mine.objects.Pairs)
            {
                var obj = pair.Value;
                var oreType = GetOreType(obj);
                if (oreType != null)
                {
                    result.Rocks.Add(new MineObject
                    {
                        TileX = (int)pair.Key.X,
                        TileY = (int)pair.Key.Y,
                        Type = oreType,
                        Health = (int)obj.MinutesUntilReady // Stones use this for health
                    });
                }
            }

            // Read monsters
            foreach (var character in mine.characters)
            {
                if (character is StardewValley.Monsters.Monster monster)
                {
                    result.Monsters.Add(new MineMonster
                    {
                        Name = monster.Name,
                        TileX = monster.TilePoint.X,
                        TileY = monster.TilePoint.Y,
                        Health = monster.Health,
                        MaxHealth = monster.MaxHealth,
                        Damage = monster.DamageToFarmer
                    });
                }
            }
        }

        return result;
    }

    private static string GetMineFloorType(int level)
    {
        if (level < 40) return "normal";
        if (level < 80) return "frozen";
        if (level < 120) return "lava";
        return "skull_cavern";
    }

    private static string GetOreType(StardewValley.Object obj)
    {
        // Stone IDs for different ore types
        return obj.ParentSheetIndex switch
        {
            751 => "Copper",
            290 => "Iron",
            764 => "Gold",
            765 => "Iridium",
            668 or 670 => "Stone",
            _ when obj.Name.Contains("Stone") => "Stone",
            _ => null
        };
    }

    // ============================================
    // STORAGE DATA READER
    // ============================================

    private StorageState ReadStorageState()
    {
        var result = new StorageState();
        if (!Context.IsWorldReady) return result;

        // Check all locations for chests
        foreach (var location in Game1.locations)
        {
            ReadChestsInLocation(location, result);

            // Check buildings
            foreach (var building in location.buildings)
            {
                var indoors = building.GetIndoors();
                if (indoors != null)
                {
                    ReadChestsInLocation(indoors, result);
                }
            }
        }

        // Read fridge (in farmhouse)
        var farmHouse = Utility.getHomeOfFarmer(Game1.player);
        if (farmHouse?.fridge.Value != null)
        {
            foreach (var item in farmHouse.fridge.Value.Items)
            {
                if (item != null)
                {
                    result.Fridge.Add(new InventoryItem
                    {
                        Slot = result.Fridge.Count,
                        Name = item.DisplayName,
                        Type = GetItemType(item),
                        Stack = item.Stack,
                        Quality = item is StardewValley.Object obj ? obj.Quality : 0
                    });
                }
            }
        }

        // Read silo hay
        var farm = Game1.getFarm();
        if (farm != null)
        {
            result.SiloHay = farm.piecesOfHay.Value;
            // Silo capacity depends on number of silos (240 per silo)
            result.SiloCapacity = farm.buildings.Count(b => b.buildingType.Value == "Silo") * 240;
        }

        return result;
    }

    private void ReadChestsInLocation(GameLocation location, StorageState result)
    {
        foreach (var pair in location.objects.Pairs)
        {
            if (pair.Value is Chest chest && chest.playerChest.Value)
            {
                var chestDetails = new ChestDetails
                {
                    Location = location.Name,
                    TileX = (int)pair.Key.X,
                    TileY = (int)pair.Key.Y,
                    Color = chest.playerChoiceColor.Value.ToString()
                };

                foreach (var item in chest.Items)
                {
                    if (item != null)
                    {
                        chestDetails.Items.Add(new InventoryItem
                        {
                            Slot = chestDetails.Items.Count,
                            Name = item.DisplayName,
                            Type = GetItemType(item),
                            Stack = item.Stack,
                            Quality = item is StardewValley.Object obj ? obj.Quality : 0
                        });
                    }
                }

                result.Chests.Add(chestDetails);
            }
        }
    }

    private static string GetItemType(Item item)
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

    protected override void Dispose(bool disposing)
    {
        if (disposing)
        {
            _httpServer?.Dispose();
        }
        base.Dispose(disposing);
    }
}
