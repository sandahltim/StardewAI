using System.Linq;
using Microsoft.Xna.Framework;
using StardewAI.GameBridge.Models;
using StardewAI.GameBridge.Pathfinding;
using StardewModdingAPI;
using StardewValley;
using StardewValley.Locations;
using StardewValley.Menus;
using StardewValley.Tools;

namespace StardewAI.GameBridge;

/// <summary>
/// Executes game actions on behalf of the AI agent.
/// Actions are queued and processed on the game's main thread.
/// </summary>
public class ActionExecutor
{
    private readonly IMonitor _monitor;
    private readonly TilePathfinder _pathfinder;

    // Current action state
    private ActionState _state = ActionState.Idle;
    private List<Point> _currentPath;
    private int _pathIndex;
    private int _waitTicksRemaining;

    public ActionState CurrentState => _state;

    public ActionExecutor(IMonitor monitor)
    {
        _monitor = monitor;
        _pathfinder = new TilePathfinder();
    }

    /// <summary>Queue an action for execution. Returns immediately with status.</summary>
    public ActionResult QueueAction(ActionCommand command)
    {
        if (!Context.IsWorldReady || Game1.player == null)
        {
            return new ActionResult { Success = false, Error = "Game not ready", State = ActionState.Failed };
        }

        _monitor.Log($"Executing action: {command.Action}", LogLevel.Debug);

        try
        {
            return command.Action?.ToLower() switch
            {
                "move" => StartMove(command.Target),
                "move_to" => StartMove(command.Target),  // Alias for move - A* pathfinding to target
                "move_direction" => MoveDirection(command.Direction, command.Tiles),
                "warp" => WarpTo(command.Target),
                "warp_to_farm" => WarpToFarm(),
                "warp_to_house" => WarpToHouse(),
                "go_to_bed" => GoToBed(),
                "warp_location" => WarpToLocation(command.Location, command.Target),
                "use_tool" => UseTool(command.Direction),
                "equip_tool" => EquipTool(command.Tool),
                "select_slot" => SelectSlot(command.Slot),
                "select_item_type" => SelectItemType(command.ItemType),
                "interact" => Interact(command.Target),
                "interact_facing" => InteractFacing(),
                "harvest" => Harvest(command.Direction),
                "ship" => ShipItem(command.Slot),
                "eat" => EatItem(command.Slot),
                "buy" => BuyItem(command.Item, command.Quantity),
                "buy_backpack" => BuyBackpack(),
                "wait" => Wait(command.Ticks),
                "face" => Face(command.Direction),
                "toggle_menu" => ToggleMenu(),
                "cancel" => Cancel(),
                "toolbar_next" => ToolbarNext(),
                "toolbar_prev" => ToolbarPrev(),
                "dismiss_menu" => DismissMenu(),
                "confirm_dialog" => ConfirmDialog(),
                // Crafting & Placement
                "craft" => CraftItem(command.Item, command.Quantity),
                "place_item" => PlaceItemAtTile(command.Direction),
                // Chest & Storage
                "open_chest" => OpenChest(command.Direction),
                "close_chest" => CloseChest(),
                "deposit_item" => DepositItem(command.Slot, command.Quantity),
                "withdraw_item" => WithdrawItem(command.Slot, command.Quantity),
                // Tool Upgrades
                "upgrade_tool" => UpgradeTool(command.Tool),
                "collect_upgraded_tool" => CollectUpgradedTool(),
                // Mining
                "enter_mine_level" => EnterMineLevel(command.Level),
                "use_ladder" => UseLadder(),
                "swing_weapon" => SwingWeapon(command.Direction),
                // Session 125: Fishing
                "cast_fishing_rod" => CastFishingRod(command.Direction),
                "start_fishing" => StartFishing(),
                // Session 125: Animals
                "pet_animal" => PetAnimal(command.Direction),
                "milk_animal" => MilkAnimal(command.Direction),
                "shear_animal" => ShearAnimal(command.Direction),
                "collect_animal_product" => CollectAnimalProduct(command.Direction),
                // Session 125: Foraging
                "shake_tree" => ShakeTree(command.Direction),
                "dig_artifact_spot" => DigArtifactSpot(command.Direction),
                // Session 125: Next mine level (reliable alternative)
                "descend_mine" => DescendMine(),
                _ => new ActionResult { Success = false, Error = $"Unknown action: {command.Action}", State = ActionState.Failed }
            };
        }
        catch (Exception ex)
        {
            _monitor.Log($"Action error: {ex.Message}", LogLevel.Error);
            return new ActionResult { Success = false, Error = ex.Message, State = ActionState.Failed };
        }
    }

    /// <summary>Called each game tick to continue multi-frame actions</summary>
    public void Update()
    {
        if (_state == ActionState.Idle || _state == ActionState.Complete || _state == ActionState.Failed)
            return;

        // Handle waiting
        if (_waitTicksRemaining > 0)
        {
            _waitTicksRemaining--;
            if (_waitTicksRemaining == 0)
            {
                _state = ActionState.Complete;
            }
            return;
        }

        // Handle pathfinding movement
        if (_state == ActionState.MovingToTarget && _currentPath != null)
        {
            ContinuePathMovement();
        }
    }

    private ActionResult StartMove(ActionTarget target)
    {
        if (target == null)
            return new ActionResult { Success = false, Error = "No target specified", State = ActionState.Failed };

        var player = Game1.player;
        var start = player.TilePoint;
        var end = new Point(target.X, target.Y);

        // Check if already at destination
        if (start == end)
        {
            return new ActionResult
            {
                Success = true,
                Message = $"Already at ({target.X}, {target.Y})",
                State = ActionState.Complete
            };
        }

        // Find path using A* pathfinding
        var path = _pathfinder.FindPath(start, end, Game1.currentLocation);

        if (path == null || path.Count == 0)
        {
            return new ActionResult { Success = false, Error = $"No path found to ({target.X}, {target.Y})", State = ActionState.Failed };
        }

        // SYNCHRONOUS: Teleport directly to destination (like MoveDirection does)
        // This works reliably - async movement via setMoving() doesn't work well
        player.Halt();
        player.forceCanMove();
        player.Position = new Microsoft.Xna.Framework.Vector2(target.X * 64f, target.Y * 64f);

        // Face direction of travel
        if (path.Count >= 2)
        {
            var lastStep = path[path.Count - 1];
            var secondLast = path[path.Count - 2];
            int direction = TilePathfinder.GetDirectionBetweenTiles(secondLast, lastStep);
            player.FacingDirection = direction;
        }

        _monitor.Log($"Moved to ({target.X}, {target.Y}) via {path.Count}-tile path", LogLevel.Debug);
        _state = ActionState.Complete;

        return new ActionResult
        {
            Success = true,
            Message = $"Moved to ({target.X}, {target.Y}), {path.Count} tiles",
            State = ActionState.Complete
        };
    }

    private void ContinuePathMovement()
    {
        var player = Game1.player;

        // Already at destination?
        if (_pathIndex >= _currentPath.Count)
        {
            _state = ActionState.Complete;
            _currentPath = null;
            return;
        }

        var currentTile = player.TilePoint;
        var targetTile = _currentPath[_pathIndex];

        // Reached this waypoint?
        if (currentTile == targetTile)
        {
            _pathIndex++;
            if (_pathIndex >= _currentPath.Count)
            {
                // Snap to tile position for consistent tool usage
                player.Position = new Microsoft.Xna.Framework.Vector2(targetTile.X * 64f, targetTile.Y * 64f);
                _state = ActionState.Complete;
                _currentPath = null;
            }
            return;
        }

        // Move toward target tile
        int direction = TilePathfinder.GetDirectionBetweenTiles(currentTile, targetTile);
        MoveInDirection(direction);
    }

    private ActionResult MoveDirection(string direction, int tiles)
    {
        int facing = TilePathfinder.DirectionToFacing(direction);
        if (facing < 0)
            return new ActionResult { Success = false, Error = $"Invalid direction: {direction}", State = ActionState.Failed };

        tiles = Math.Max(1, Math.Min(tiles, 10)); // Clamp 1-10

        var player = Game1.player;
        var location = Game1.currentLocation;
        var start = player.TilePoint;
        var delta = GetDirectionDelta(facing);

        // Find how far we can actually move (check passability using pathfinder's thorough check)
        int actualTiles = 0;
        Point finalTile = start;
        
        for (int i = 1; i <= tiles; i++)
        {
            var nextTile = new Point(start.X + delta.X * i, start.Y + delta.Y * i);

            // Use pathfinder's thorough passability check (includes objects, map bounds, etc.)
            if (!_pathfinder.IsTilePassable(nextTile, location))
            {
                _monitor.Log($"Tile ({nextTile.X}, {nextTile.Y}) is blocked, stopping at {actualTiles} tiles", LogLevel.Debug);
                break;
            }
            actualTiles++;
            finalTile = nextTile;
        }

        if (actualTiles == 0)
        {
            return new ActionResult
            {
                Success = false,
                Error = $"Path blocked - cannot move {direction}",
                State = ActionState.Failed
            };
        }

        // SYNCHRONOUS MOVEMENT: Move directly to final tile (like WarpTo but with collision check)
        // This ensures movement works even when game loop isn't processing setMoving flags
        player.FacingDirection = facing;
        player.Halt();
        player.forceCanMove();
        player.Position = new Microsoft.Xna.Framework.Vector2(finalTile.X * 64f, finalTile.Y * 64f);
        
        _monitor.Log($"Moved {direction} {actualTiles} tiles to ({finalTile.X}, {finalTile.Y})", LogLevel.Debug);
        _state = ActionState.Complete;

        return new ActionResult
        {
            Success = true,
            Message = $"Moved {direction} {actualTiles} tiles",
            State = ActionState.Complete
        };
    }

    private void MoveInDirection(int direction)
    {
        var player = Game1.player;
        player.FacingDirection = direction;

        // Get current target tile from path
        if (_currentPath == null || _pathIndex >= _currentPath.Count)
            return;

        var targetTile = _currentPath[_pathIndex];
        var currentTile = player.TilePoint;

        // Check if we've reached the target tile - snap to position for consistency
        if (currentTile.X == targetTile.X && currentTile.Y == targetTile.Y)
        {
            // Snap to tile position to prevent tool misalignment from edge positions
            player.Position = new Microsoft.Xna.Framework.Vector2(targetTile.X * 64f, targetTile.Y * 64f);
            return;
        }

        // Use game's movement system - this respects collisions and triggers warps
        // Set movement flags instead of directly setting position
        player.setMoving((byte)(1 << direction)); // 1=up, 2=right, 4=down, 8=left
        player.canMove = true;
        player.running = false;

        // Also try the built-in movement check
        var location = Game1.currentLocation;
        var nextPos = player.Position;
        float speed = 4f;
        switch (direction)
        {
            case 0: nextPos.Y -= speed; break; // Up
            case 1: nextPos.X += speed; break; // Right
            case 2: nextPos.Y += speed; break; // Down
            case 3: nextPos.X -= speed; break; // Left
        }

        // Check collision before moving
        var nextBounds = new Microsoft.Xna.Framework.Rectangle(
            (int)nextPos.X, (int)nextPos.Y,
            player.GetBoundingBox().Width, player.GetBoundingBox().Height);

        if (!location.isCollidingPosition(nextBounds, Game1.viewport, true, 0, false, player))
        {
            player.Position = nextPos;
        }
        else
        {
            // Blocked - stop movement
            player.Halt();
            _state = ActionState.Complete;
        }
    }

    private static Point GetDirectionDelta(int direction)
    {
        return direction switch
        {
            0 => new Point(0, -1),  // Up
            1 => new Point(1, 0),   // Right
            2 => new Point(0, 1),   // Down
            3 => new Point(-1, 0),  // Left
            _ => Point.Zero
        };
    }

    private ActionResult UseTool(string direction)
    {
        var player = Game1.player;
        var tool = player.CurrentTool;
        var activeObject = player.ActiveObject;

        // Set facing direction if specified
        if (!string.IsNullOrEmpty(direction))
        {
            int facing = TilePathfinder.DirectionToFacing(direction);
            if (facing >= 0) player.FacingDirection = facing;
        }

        // SAFETY: Prevent axe/pickaxe from destroying planted crops
        if (tool is Axe || tool is Pickaxe)
        {
            var facingDir = player.FacingDirection;
            var delta = GetDirectionDelta(facingDir);
            int targetX = player.TilePoint.X + delta.X;
            int targetY = player.TilePoint.Y + delta.Y;
            var facingTile = new Microsoft.Xna.Framework.Vector2(targetX, targetY);

            var location = Game1.currentLocation;
            if (location.terrainFeatures.TryGetValue(facingTile, out var feature) &&
                feature is StardewValley.TerrainFeatures.HoeDirt hoeDirt &&
                hoeDirt.crop != null)
            {
                _monitor.Log($"BLOCKED: {tool.DisplayName} would destroy crop at ({targetX}, {targetY})", LogLevel.Warn);
                return new ActionResult
                {
                    Success = false,
                    Error = $"Blocked: {tool.DisplayName} would destroy planted crop",
                    State = ActionState.Failed
                };
            }
        }

        // Check if holding a tool
        if (tool != null)
        {
            // Use the tool
            player.BeginUsingTool();

            _state = ActionState.WaitingForAnimation;
            _waitTicksRemaining = 30; // Wait for animation

            return new ActionResult
            {
                Success = true,
                Message = $"Using {tool.DisplayName}",
                State = ActionState.PerformingAction
            };
        }
        // Check if holding an object (seeds, items to place)
        else if (activeObject != null)
        {
            // Get tile in front of player
            var facingDir = player.FacingDirection;
            int targetX = player.TilePoint.X + (facingDir == 1 ? 1 : facingDir == 3 ? -1 : 0);
            int targetY = player.TilePoint.Y + (facingDir == 2 ? 1 : facingDir == 0 ? -1 : 0);
            var targetTile = new Microsoft.Xna.Framework.Vector2(targetX, targetY);

            // Try to place/use the object
            bool success = Utility.tryToPlaceItem(player.currentLocation, activeObject, targetX * 64, targetY * 64);

            if (success)
            {
                // Note: Utility.tryToPlaceItem handles item consumption internally
                // Do NOT manually decrement stack - that causes double consumption!

                return new ActionResult
                {
                    Success = true,
                    Message = $"Placed {activeObject.DisplayName}",
                    State = ActionState.PerformingAction
                };
            }
            else
            {
                return new ActionResult
                {
                    Success = false,
                    Error = $"Cannot place {activeObject.DisplayName} here",
                    State = ActionState.Failed
                };
            }
        }
        else
        {
            return new ActionResult { Success = false, Error = "No tool or item equipped", State = ActionState.Failed };
        }
    }

    private ActionResult EquipTool(string toolName)
    {
        var player = Game1.player;

        for (int i = 0; i < player.Items.Count; i++)
        {
            var item = player.Items[i];
            if (item != null && item.DisplayName.Equals(toolName, StringComparison.OrdinalIgnoreCase))
            {
                player.CurrentToolIndex = i;
                return new ActionResult
                {
                    Success = true,
                    Message = $"Equipped {item.DisplayName}",
                    State = ActionState.Complete
                };
            }
        }

        // Try partial match
        for (int i = 0; i < player.Items.Count; i++)
        {
            var item = player.Items[i];
            if (item != null && item.DisplayName.Contains(toolName, StringComparison.OrdinalIgnoreCase))
            {
                player.CurrentToolIndex = i;
                return new ActionResult
                {
                    Success = true,
                    Message = $"Equipped {item.DisplayName}",
                    State = ActionState.Complete
                };
            }
        }

        return new ActionResult { Success = false, Error = $"Tool not found: {toolName}", State = ActionState.Failed };
    }

    private ActionResult SelectSlot(int slot)
    {
        if (slot < 0 || slot >= 12)
            return new ActionResult { Success = false, Error = $"Invalid slot: {slot}", State = ActionState.Failed };

        Game1.player.CurrentToolIndex = slot;

        return new ActionResult
        {
            Success = true,
            Message = $"Selected slot {slot}",
            State = ActionState.Complete
        };
    }

    private ActionResult SelectItemType(string itemType)
    {
        if (string.IsNullOrEmpty(itemType))
            return new ActionResult { Success = false, Error = "No item type specified", State = ActionState.Failed };

        var player = Game1.player;
        var searchType = itemType.ToLower().Trim();

        for (int i = 0; i < player.Items.Count; i++)
        {
            var item = player.Items[i];
            if (item == null) continue;

            bool match = searchType switch
            {
                "seed" or "seeds" => item is StardewValley.Object obj && obj.Category == StardewValley.Object.SeedsCategory,
                "vegetable" or "vegetables" or "crop" or "crops" => item is StardewValley.Object obj && obj.Category == StardewValley.Object.VegetableCategory,
                "fruit" or "fruits" => item is StardewValley.Object obj && obj.Category == StardewValley.Object.FruitsCategory,
                "fish" => item is StardewValley.Object obj && obj.Category == StardewValley.Object.FishCategory,
                "food" or "edible" => item is StardewValley.Object obj && obj.Edibility > 0,
                "tool" or "tools" => item is Tool,
                "sellable" => item is StardewValley.Object obj && obj.canBeShipped(),
                // Fallback: match by item name (case-insensitive) - enables "Watering Can", "Hoe", etc.
                _ => item.DisplayName.ToLower().Contains(searchType) ||
                     item.Name.ToLower().Contains(searchType)
            };

            if (match)
            {
                player.CurrentToolIndex = i;
                _monitor.Log($"SelectItemType: Found {item.DisplayName} at slot {i}", LogLevel.Debug);
                return new ActionResult
                {
                    Success = true,
                    Message = $"Selected {item.DisplayName} (slot {i})",
                    State = ActionState.Complete
                };
            }
        }

        return new ActionResult
        {
            Success = false,
            Error = $"No {itemType} found in inventory",
            State = ActionState.Failed
        };
    }

    private ActionResult Interact(ActionTarget target)
    {
        if (target == null)
            return InteractFacing();

        var player = Game1.player;
        var targetPos = new Vector2(target.X, target.Y);

        // Check if adjacent, if not start pathfinding
        var playerTile = player.TilePoint;
        int distance = Math.Abs(playerTile.X - target.X) + Math.Abs(playerTile.Y - target.Y);

        if (distance > 1)
        {
            // Need to move closer first
            return StartMove(target);
        }

        // Face the target
        int direction = TilePathfinder.GetDirectionBetweenTiles(playerTile, new Point(target.X, target.Y));
        player.FacingDirection = direction;

        // Perform interaction
        var location = Game1.currentLocation;
        location.checkAction(new xTile.Dimensions.Location(target.X, target.Y), Game1.viewport, player);

        return new ActionResult
        {
            Success = true,
            Message = $"Interacted at ({target.X}, {target.Y})",
            State = ActionState.Complete
        };
    }

    private ActionResult InteractFacing()
    {
        var player = Game1.player;
        var facingTile = player.GetGrabTile();

        var location = Game1.currentLocation;
        location.checkAction(
            new xTile.Dimensions.Location((int)facingTile.X, (int)facingTile.Y),
            Game1.viewport,
            player
        );

        return new ActionResult
        {
            Success = true,
            Message = "Interacted with facing tile",
            State = ActionState.Complete
        };
    }

    private ActionResult Harvest(string direction)
    {
        var player = Game1.player;
        var location = Game1.currentLocation;

        // Set facing direction if specified
        if (!string.IsNullOrEmpty(direction))
        {
            int facing = TilePathfinder.DirectionToFacing(direction);
            if (facing >= 0) player.FacingDirection = facing;
        }

        // Calculate the tile we're facing (GetGrabTile was returning player's own tile)
        var playerTile = player.TilePoint;
        var delta = GetDirectionDelta(player.FacingDirection);
        int tileX = playerTile.X + delta.X;
        int tileY = playerTile.Y + delta.Y;
        var facingTile = new Microsoft.Xna.Framework.Vector2(tileX, tileY);

        // DEBUG: Log what we're checking
        string facingCardinal = TilePathfinder.FacingToCardinal(player.FacingDirection);
        _monitor.Log($"Harvest: Player at ({playerTile.X}, {playerTile.Y}) facing {facingCardinal}", LogLevel.Debug);
        _monitor.Log($"Harvest: Facing tile = ({tileX}, {tileY})", LogLevel.Debug);

        // DEBUG: Check what terrain features exist nearby
        foreach (var kvp in location.terrainFeatures.Pairs)
        {
            var dist = Math.Abs(kvp.Key.X - player.TilePoint.X) + Math.Abs(kvp.Key.Y - player.TilePoint.Y);
            if (dist <= 2)
            {
                _monitor.Log($"Harvest: TerrainFeature at ({kvp.Key.X}, {kvp.Key.Y}): {kvp.Value.GetType().Name}", LogLevel.Debug);
            }
        }

        // Check if there's a HoeDirt with a harvestable crop at that tile
        if (location.terrainFeatures.TryGetValue(facingTile, out var feature) &&
            feature is StardewValley.TerrainFeatures.HoeDirt hoeDirt)
        {
            var crop = hoeDirt.crop;
            if (crop != null && crop.currentPhase.Value >= crop.phaseDays.Count - 1)
            {
                // Crop is ready - trigger harvest via performUseAction
                bool harvested = hoeDirt.performUseAction(facingTile);

                if (harvested)
                {
                    return new ActionResult
                    {
                        Success = true,
                        Message = $"Harvested crop at ({tileX}, {tileY})",
                        State = ActionState.Complete
                    };
                }
                else
                {
                    // Try alternate harvest method - direct crop harvest
                    bool altHarvest = crop.harvest(tileX, tileY, hoeDirt);
                    return new ActionResult
                    {
                        Success = altHarvest,
                        Message = altHarvest ? $"Harvested crop at ({tileX}, {tileY})" : "Harvest failed",
                        State = altHarvest ? ActionState.Complete : ActionState.Failed
                    };
                }
            }
            else
            {
                return new ActionResult
                {
                    Success = false,
                    Error = crop == null ? "No crop at this tile" : "Crop not ready for harvest",
                    State = ActionState.Failed
                };
            }
        }
        else
        {
            return new ActionResult
            {
                Success = false,
                Error = "No farmable soil at this tile",
                State = ActionState.Failed
            };
        }
    }

    private ActionResult ShipItem(int slot)
    {
        var player = Game1.player;
        var farm = Game1.getFarm();

        if (farm == null)
        {
            return new ActionResult
            {
                Success = false,
                Error = "Not on farm - cannot access shipping bin",
                State = ActionState.Failed
            };
        }

        // Get item from specified slot (or current slot if -1)
        int targetSlot = slot >= 0 ? slot : player.CurrentToolIndex;

        if (targetSlot < 0 || targetSlot >= player.Items.Count)
        {
            return new ActionResult
            {
                Success = false,
                Error = $"Invalid slot {targetSlot}",
                State = ActionState.Failed
            };
        }

        var item = player.Items[targetSlot];

        if (item == null)
        {
            return new ActionResult
            {
                Success = false,
                Error = $"No item in slot {targetSlot}",
                State = ActionState.Failed
            };
        }

        // Check if item can be shipped (must be an Object, not a tool)
        if (item is not StardewValley.Object obj)
        {
            return new ActionResult
            {
                Success = false,
                Error = $"{item.Name} cannot be shipped",
                State = ActionState.Failed
            };
        }

        string itemName = item.Name;
        int quantity = item.Stack;

        // Add to shipping bin
        farm.getShippingBin(player).Add(obj);

        // Remove from inventory
        player.Items[targetSlot] = null;

        _monitor.Log($"Shipped {quantity}x {itemName}", LogLevel.Info);

        return new ActionResult
        {
            Success = true,
            Message = $"Shipped {quantity}x {itemName}",
            State = ActionState.Complete
        };
    }

    private ActionResult EatItem(int slot)
    {
        var player = Game1.player;

        // Get item from specified slot (or current slot if -1)
        int targetSlot = slot >= 0 ? slot : player.CurrentToolIndex;

        if (targetSlot < 0 || targetSlot >= player.Items.Count)
        {
            return new ActionResult
            {
                Success = false,
                Error = $"Invalid slot {targetSlot}",
                State = ActionState.Failed
            };
        }

        var item = player.Items[targetSlot];

        if (item == null)
        {
            return new ActionResult
            {
                Success = false,
                Error = $"No item in slot {targetSlot}",
                State = ActionState.Failed
            };
        }

        // Check if item is edible (must be an Object with edibility > 0)
        if (item is not StardewValley.Object obj || obj.Edibility <= 0)
        {
            return new ActionResult
            {
                Success = false,
                Error = $"{item.Name} is not edible",
                State = ActionState.Failed
            };
        }

        string itemName = item.Name;
        int energyRestored = obj.Edibility;
        int healthRestored = (int)(obj.Edibility * 0.45f);

        // Consume the item
        player.eatObject(obj, false);

        // Reduce stack or remove
        if (item.Stack > 1)
        {
            item.Stack--;
        }
        else
        {
            player.Items[targetSlot] = null;
        }

        _monitor.Log($"Ate {itemName}: +{energyRestored} energy, +{healthRestored} health", LogLevel.Info);

        return new ActionResult
        {
            Success = true,
            Message = $"Ate {itemName}: +{energyRestored} energy",
            State = ActionState.Complete
        };
    }

    // Shop catalogs: maps item name (lowercase) to (itemId, price)
    private static readonly Dictionary<string, Dictionary<string, (string Id, int Price)>> ShopCatalogs = new()
    {
        ["SeedShop"] = new() // Pierre's General Store
        {
            ["parsnip seeds"] = ("(O)472", 20),
            ["bean starter"] = ("(O)473", 60),
            ["cauliflower seeds"] = ("(O)474", 80),
            ["potato seeds"] = ("(O)475", 50),
            ["tulip bulb"] = ("(O)427", 20),
            ["kale seeds"] = ("(O)477", 70),
            ["jazz seeds"] = ("(O)429", 30),
            ["garlic seeds"] = ("(O)476", 40),
            ["rice shoot"] = ("(O)273", 40),
            // Summer
            ["melon seeds"] = ("(O)479", 80),
            ["tomato seeds"] = ("(O)480", 50),
            ["blueberry seeds"] = ("(O)481", 80),
            ["pepper seeds"] = ("(O)482", 40),
            ["wheat seeds"] = ("(O)483", 10),
            ["radish seeds"] = ("(O)484", 40),
            ["red cabbage seeds"] = ("(O)485", 100),
            ["starfruit seeds"] = ("(O)486", 400),
            ["corn seeds"] = ("(O)487", 150),
            ["sunflower seeds"] = ("(O)431", 200),
            ["poppy seeds"] = ("(O)453", 100),
            // Fall
            ["eggplant seeds"] = ("(O)488", 20),
            ["pumpkin seeds"] = ("(O)490", 100),
            ["bok choy seeds"] = ("(O)491", 50),
            ["yam seeds"] = ("(O)492", 60),
            ["cranberry seeds"] = ("(O)493", 240),
            ["beet seeds"] = ("(O)494", 20),
            ["fairy seeds"] = ("(O)425", 200),
            ["amaranth seeds"] = ("(O)299", 70),
            ["grape starter"] = ("(O)301", 60),
            ["artichoke seeds"] = ("(O)489", 30),
            // Basic supplies
            ["grass starter"] = ("(O)297", 100),
            ["sugar"] = ("(O)245", 100),
            ["wheat flour"] = ("(O)246", 100),
            ["oil"] = ("(O)247", 200),
            ["vinegar"] = ("(O)419", 200),
        },
        ["AnimalShop"] = new() // Marnie's Ranch
        {
            ["hay"] = ("(O)178", 50),
            ["heater"] = ("(BC)104", 2000),
        },
        ["FishShop"] = new() // Willy's
        {
            ["trout soup"] = ("(O)219", 250),
            ["bait"] = ("(O)685", 5),
        },
    };

    // Shops valid for purchasing (location name -> shop name)
    private static readonly Dictionary<string, string> LocationToShop = new()
    {
        ["SeedShop"] = "SeedShop",
        ["AnimalShop"] = "AnimalShop",
        ["FishShop"] = "FishShop",
    };

    private ActionResult BuyItem(string itemName, int quantity)
    {
        var player = Game1.player;
        var locationName = player.currentLocation?.Name;

        // Check if in a valid shop location
        if (string.IsNullOrEmpty(locationName) || !LocationToShop.TryGetValue(locationName, out var shopName))
        {
            return new ActionResult
            {
                Success = false,
                Error = $"Not in a shop (current: {locationName ?? "unknown"}). Valid shops: SeedShop (Pierre's), AnimalShop (Marnie's), FishShop (Willy's)",
                State = ActionState.Failed
            };
        }

        // Get shop catalog
        if (!ShopCatalogs.TryGetValue(shopName, out var catalog))
        {
            return new ActionResult
            {
                Success = false,
                Error = $"Shop {shopName} has no catalog",
                State = ActionState.Failed
            };
        }

        // Look up item (case-insensitive)
        var searchKey = itemName?.ToLower().Trim() ?? "";
        if (!catalog.TryGetValue(searchKey, out var itemInfo))
        {
            var available = string.Join(", ", catalog.Keys.Take(5)) + (catalog.Count > 5 ? "..." : "");
            return new ActionResult
            {
                Success = false,
                Error = $"'{itemName}' not found at {shopName}. Available: {available}",
                State = ActionState.Failed
            };
        }

        // Calculate total cost
        int qty = Math.Max(1, quantity);
        int totalCost = itemInfo.Price * qty;

        // Check if player has enough money
        if (player.Money < totalCost)
        {
            return new ActionResult
            {
                Success = false,
                Error = $"Not enough gold. Need {totalCost}g for {qty}x {itemName}, have {player.Money}g",
                State = ActionState.Failed
            };
        }

        // Create the item
        var newItem = ItemRegistry.Create(itemInfo.Id, qty);
        if (newItem == null)
        {
            return new ActionResult
            {
                Success = false,
                Error = $"Failed to create item {itemInfo.Id}",
                State = ActionState.Failed
            };
        }

        // Add to inventory
        bool added = player.addItemToInventoryBool(newItem);
        if (!added)
        {
            return new ActionResult
            {
                Success = false,
                Error = "Inventory full - cannot add item",
                State = ActionState.Failed
            };
        }

        // Deduct money
        player.Money -= totalCost;

        _monitor.Log($"Bought {qty}x {newItem.DisplayName} for {totalCost}g", LogLevel.Info);

        return new ActionResult
        {
            Success = true,
            Message = $"Bought {qty}x {newItem.DisplayName} for {totalCost}g (balance: {player.Money}g)",
            State = ActionState.Complete
        };
    }

    private ActionResult BuyBackpack()
    {
        var player = Game1.player;
        var locationName = player.currentLocation?.Name;

        if (locationName != "SeedShop")
        {
            return new ActionResult
            {
                Success = false,
                Error = $"Not at Pierre's (current: {locationName ?? "unknown"}). Must be in SeedShop to buy backpack.",
                State = ActionState.Failed
            };
        }

        int currentSlots = GetMaxItems(player);
        int nextSlots;
        int cost;

        if (currentSlots <= 12)
        {
            nextSlots = 24;
            cost = 2000;
        }
        else if (currentSlots <= 24)
        {
            nextSlots = 36;
            cost = 10000;
        }
        else
        {
            return new ActionResult
            {
                Success = false,
                Error = $"Backpack already maxed ({currentSlots} slots)",
                State = ActionState.Failed
            };
        }

        if (player.Money < cost)
        {
            return new ActionResult
            {
                Success = false,
                Error = $"Not enough gold. Need {cost}g, have {player.Money}g",
                State = ActionState.Failed
            };
        }

        if (!SetMaxItems(player, nextSlots))
        {
            return new ActionResult
            {
                Success = false,
                Error = "Failed to update backpack size",
                State = ActionState.Failed
            };
        }

        player.Money -= cost;

        _monitor.Log($"Backpack upgraded to {nextSlots} slots for {cost}g", LogLevel.Info);

        return new ActionResult
        {
            Success = true,
            Message = $"Backpack upgraded to {nextSlots} slots for {cost}g (balance: {player.Money}g)",
            State = ActionState.Complete
        };
    }

    private static int GetMaxItems(Farmer player)
    {
        var playerType = player.GetType();
        var prop = playerType.GetProperty("MaxItems");
        if (prop != null)
        {
            var value = prop.GetValue(player);
            if (value is int intValue)
                return intValue;
            var netValue = value?.GetType().GetProperty("Value");
            if (netValue != null && netValue.PropertyType == typeof(int))
                return (int)netValue.GetValue(value);
        }

        var field = playerType.GetField("maxItems");
        if (field != null)
        {
            var value = field.GetValue(player);
            if (value is int intValue)
                return intValue;
            var netValue = value?.GetType().GetProperty("Value");
            if (netValue != null && netValue.PropertyType == typeof(int))
                return (int)netValue.GetValue(value);
        }

        return player.Items?.Count ?? 12;
    }

    private static bool SetMaxItems(Farmer player, int value)
    {
        var playerType = player.GetType();
        var prop = playerType.GetProperty("MaxItems");
        if (prop != null && prop.CanWrite)
        {
            if (prop.PropertyType == typeof(int))
            {
                prop.SetValue(player, value);
                return true;
            }
            var propValue = prop.GetValue(player);
            var netValue = propValue?.GetType().GetProperty("Value");
            if (netValue != null && netValue.CanWrite && netValue.PropertyType == typeof(int))
            {
                netValue.SetValue(propValue, value);
                return true;
            }
        }

        var field = playerType.GetField("maxItems");
        if (field != null)
        {
            if (field.FieldType == typeof(int))
            {
                field.SetValue(player, value);
                return true;
            }
            var fieldValue = field.GetValue(player);
            var netValue = fieldValue?.GetType().GetProperty("Value");
            if (netValue != null && netValue.CanWrite && netValue.PropertyType == typeof(int))
            {
                netValue.SetValue(fieldValue, value);
                return true;
            }
        }

        return false;
    }

    private ActionResult UpgradeTool(string toolName)
    {
        var player = Game1.player;
        var locationName = player.currentLocation?.Name;

        // Must be at blacksmith
        if (locationName != "Blacksmith")
        {
            return new ActionResult
            {
                Success = false,
                Error = $"Not at Blacksmith (current: {locationName ?? "unknown"}). Go to Clint's shop.",
                State = ActionState.Failed
            };
        }

        // Already upgrading a tool?
        if (player.toolBeingUpgraded.Value != null)
        {
            var currentUpgrade = player.toolBeingUpgraded.Value;
            return new ActionResult
            {
                Success = false,
                Error = $"Already upgrading {currentUpgrade.DisplayName}. {player.daysLeftForToolUpgrade.Value} day(s) remaining.",
                State = ActionState.Failed
            };
        }

        // Find the tool in inventory
        Tool tool = null;
        foreach (var item in player.Items)
        {
            if (item is Tool t && t.DisplayName.ToLower().Contains(toolName.ToLower()))
            {
                tool = t;
                break;
            }
        }

        if (tool == null)
        {
            return new ActionResult
            {
                Success = false,
                Error = $"Tool '{toolName}' not found in inventory",
                State = ActionState.Failed
            };
        }

        // Get current upgrade level and check if already maxed
        int currentLevel = tool.UpgradeLevel;
        if (currentLevel >= 4)
        {
            return new ActionResult
            {
                Success = false,
                Error = $"{tool.DisplayName} is already at Iridium level (max)",
                State = ActionState.Failed
            };
        }

        // Calculate costs based on next upgrade level
        int goldCost;
        string barName;
        int barCount = 5;

        switch (currentLevel)
        {
            case 0: // Basic -> Copper
                goldCost = 2000;
                barName = "Copper Bar";
                break;
            case 1: // Copper -> Steel
                goldCost = 5000;
                barName = "Iron Bar";
                break;
            case 2: // Steel -> Gold
                goldCost = 10000;
                barName = "Gold Bar";
                break;
            case 3: // Gold -> Iridium
                goldCost = 25000;
                barName = "Iridium Bar";
                break;
            default:
                return new ActionResult
                {
                    Success = false,
                    Error = $"Invalid tool level: {currentLevel}",
                    State = ActionState.Failed
                };
        }

        // Check gold
        if (player.Money < goldCost)
        {
            return new ActionResult
            {
                Success = false,
                Error = $"Not enough gold. Need {goldCost}g, have {player.Money}g",
                State = ActionState.Failed
            };
        }

        // Count bars in inventory
        int barCount_owned = 0;
        foreach (var item in player.Items)
        {
            if (item != null && item.Name == barName)
            {
                barCount_owned += item.Stack;
            }
        }

        if (barCount_owned < barCount)
        {
            return new ActionResult
            {
                Success = false,
                Error = $"Not enough {barName}. Need {barCount}, have {barCount_owned}",
                State = ActionState.Failed
            };
        }

        // Remove bars from inventory
        int barsToRemove = barCount;
        for (int i = 0; i < player.Items.Count && barsToRemove > 0; i++)
        {
            var item = player.Items[i];
            if (item != null && item.Name == barName)
            {
                int removeFromStack = Math.Min(item.Stack, barsToRemove);
                item.Stack -= removeFromStack;
                barsToRemove -= removeFromStack;
                if (item.Stack <= 0)
                {
                    player.Items[i] = null;
                }
            }
        }

        // Deduct gold
        player.Money -= goldCost;

        // Upgrade the tool - game expects us to remove from inventory and set toolBeingUpgraded
        player.removeItemFromInventory(tool);
        tool.UpgradeLevel = currentLevel + 1;
        player.toolBeingUpgraded.Value = tool;
        player.daysLeftForToolUpgrade.Value = 2;

        string[] levelNames = { "Basic", "Copper", "Steel", "Gold", "Iridium" };
        string newLevelName = levelNames[currentLevel + 1];

        _monitor.Log($"Tool upgrade started: {tool.DisplayName} -> {newLevelName} for {goldCost}g + {barCount} {barName}", LogLevel.Info);

        return new ActionResult
        {
            Success = true,
            Message = $"Upgrading {tool.DisplayName} to {newLevelName} for {goldCost}g + {barCount} {barName}. Ready in 2 days.",
            State = ActionState.Complete
        };
    }

    private ActionResult CollectUpgradedTool()
    {
        var player = Game1.player;
        var locationName = player.currentLocation?.Name;

        // Must be at blacksmith
        if (locationName != "Blacksmith")
        {
            return new ActionResult
            {
                Success = false,
                Error = $"Not at Blacksmith (current: {locationName ?? "unknown"}). Go to Clint's shop.",
                State = ActionState.Failed
            };
        }

        // Check if there's a tool being upgraded
        var upgradingTool = player.toolBeingUpgraded.Value;
        if (upgradingTool == null)
        {
            return new ActionResult
            {
                Success = false,
                Error = "No tool is currently being upgraded",
                State = ActionState.Failed
            };
        }

        // Check if upgrade is complete
        int daysLeft = player.daysLeftForToolUpgrade.Value;
        if (daysLeft > 0)
        {
            return new ActionResult
            {
                Success = false,
                Error = $"{upgradingTool.DisplayName} not ready yet. {daysLeft} day(s) remaining.",
                State = ActionState.Failed
            };
        }

        // Add tool back to inventory
        string toolName = upgradingTool.DisplayName;
        if (!player.addItemToInventoryBool(upgradingTool))
        {
            return new ActionResult
            {
                Success = false,
                Error = $"Inventory full. Cannot collect {toolName}.",
                State = ActionState.Failed
            };
        }

        // Clear the upgrade state
        player.toolBeingUpgraded.Value = null;
        player.daysLeftForToolUpgrade.Value = 0;

        _monitor.Log($"Collected upgraded tool: {toolName}", LogLevel.Info);

        return new ActionResult
        {
            Success = true,
            Message = $"Collected {toolName} from Clint!",
            State = ActionState.Complete
        };
    }

    // ============================================
    // MINING ACTIONS
    // ============================================

    private ActionResult EnterMineLevel(int level)
    {
        var player = Game1.player;
        var location = player.currentLocation;

        // Level 0 = mine entrance, levels 1-120 = regular mine, 121+ = skull cavern
        if (level < 0)
        {
            return new ActionResult
            {
                Success = false,
                Error = $"Invalid mine level: {level}. Must be >= 0.",
                State = ActionState.Failed
            };
        }

        // Session 125: Simplified - always allow entering mine levels
        // The agent handles the logic of when to descend
        _monitor.Log($"EnterMineLevel: Entering level {level} from {location?.Name ?? "unknown"}", LogLevel.Info);

        // If not in mines at all, warp to mine entrance first
        if (location?.Name != "Mine" && location is not MineShaft)
        {
            _monitor.Log($"EnterMineLevel: Warping to Mine first", LogLevel.Debug);
            Game1.warpFarmer("Mine", 13, 10, false);

            // If level > 0, still need to enter the mine level
            if (level == 0)
            {
                return new ActionResult
                {
                    Success = true,
                    Message = "Warped to mine entrance",
                    State = ActionState.Complete
                };
            }
        }

        // Enter the mine level directly
        // Game1.enterMine handles creating the MineShaft location
        Game1.enterMine(level);

        _monitor.Log($"Entered mine level {level}", LogLevel.Info);

        return new ActionResult
        {
            Success = true,
            Message = $"Entered mine level {level}",
            State = ActionState.Complete
        };
    }

    private ActionResult UseLadder()
    {
        var player = Game1.player;
        var location = player.currentLocation;

        // Must be in a mine
        if (location is not MineShaft mine)
        {
            return new ActionResult
            {
                Success = false,
                Error = $"Not in a mine (current: {location?.Name ?? "unknown"})",
                State = ActionState.Failed
            };
        }

        // Find ladder or shaft at player's position or adjacent tiles
        Point playerTile = player.TilePoint;
        Point? ladderPos = null;
        bool isShaft = false;

        // Check player tile and adjacent tiles
        Point[] checkTiles = {
            playerTile,
            new Point(playerTile.X, playerTile.Y - 1),
            new Point(playerTile.X, playerTile.Y + 1),
            new Point(playerTile.X - 1, playerTile.Y),
            new Point(playerTile.X + 1, playerTile.Y)
        };

        // Session 129: Helper to check for ladder/shaft in an object
        StardewValley.Object CheckTileForLadder(Vector2 key)
        {
            // Check property (uppercase Objects) - pre-existing objects
            if (mine.Objects.TryGetValue(key, out var obj))
            {
                if (obj.Name == "Ladder" || obj.Name == "Shaft")
                    return obj;
            }
            // Also check field (lowercase objects) - runtime spawned objects
            if (mine.objects.TryGetValue(key, out var obj2))
            {
                if (obj2.Name == "Ladder" || obj2.Name == "Shaft")
                    return obj2;
            }
            return null;
        }

        foreach (var tile in checkTiles)
        {
            var key = new Vector2(tile.X, tile.Y);
            var obj = CheckTileForLadder(key);
            if (obj != null)
            {
                ladderPos = tile;
                isShaft = obj.Name == "Shaft";
                break;
            }
        }

        if (ladderPos == null)
        {
            return new ActionResult
            {
                Success = false,
                Error = "No ladder or shaft found nearby. Break more rocks to spawn one.",
                State = ActionState.Failed
            };
        }

        // Move player to ladder tile if not already there
        if (playerTile != ladderPos.Value)
        {
            player.setTileLocation(new Vector2(ladderPos.Value.X, ladderPos.Value.Y));
        }

        // Descend: shaft goes 3-8 levels, ladder goes 1
        int currentLevel = mine.mineLevel;
        int nextLevel = isShaft ? currentLevel + Game1.random.Next(3, 9) : currentLevel + 1;

        Game1.enterMine(nextLevel);

        _monitor.Log($"Used {(isShaft ? "shaft" : "ladder")} to descend to level {nextLevel}", LogLevel.Info);

        return new ActionResult
        {
            Success = true,
            Message = $"Descended to level {nextLevel} via {(isShaft ? "shaft" : "ladder")}",
            State = ActionState.Complete
        };
    }

    private ActionResult SwingWeapon(string direction)
    {
        var player = Game1.player;

        // Get the current tool/weapon
        var tool = player.CurrentTool;
        if (tool == null)
        {
            return new ActionResult
            {
                Success = false,
                Error = "No tool equipped. Select a weapon first.",
                State = ActionState.Failed
            };
        }

        // Check if it's a melee weapon
        if (tool is not MeleeWeapon weapon)
        {
            return new ActionResult
            {
                Success = false,
                Error = $"Current tool ({tool.DisplayName}) is not a weapon.",
                State = ActionState.Failed
            };
        }

        // Set facing direction
        if (!string.IsNullOrEmpty(direction))
        {
            int facing = TilePathfinder.DirectionToFacing(direction);
            if (facing >= 0)
            {
                player.FacingDirection = facing;
            }
        }

        // Perform the weapon swing
        // Use the weapon at the player's position
        var playerCenter = player.GetBoundingBox().Center;
        weapon.setFarmerAnimating(player);

        // DoFunction triggers the actual attack
        weapon.DoFunction(player.currentLocation, playerCenter.X, playerCenter.Y, 1, player);

        _monitor.Log($"Swung {weapon.DisplayName} facing {player.FacingDirection}", LogLevel.Debug);

        return new ActionResult
        {
            Success = true,
            Message = $"Attacked with {weapon.DisplayName}",
            State = ActionState.Complete
        };
    }

    private ActionResult Wait(int ticks)
    {
        _waitTicksRemaining = Math.Max(1, Math.Min(ticks, 600)); // 1-600 ticks (10 seconds max)
        _state = ActionState.WaitingForAnimation;

        return new ActionResult
        {
            Success = true,
            Message = $"Waiting {_waitTicksRemaining} ticks",
            State = ActionState.WaitingForAnimation
        };
    }

    private ActionResult Face(string direction)
    {
        int facing = TilePathfinder.DirectionToFacing(direction);
        if (facing < 0)
            return new ActionResult { Success = false, Error = $"Invalid direction: {direction}", State = ActionState.Failed };

        Game1.player.FacingDirection = facing;

        return new ActionResult
        {
            Success = true,
            Message = $"Facing {direction}",
            State = ActionState.Complete
        };
    }

    private ActionResult ToggleMenu()
    {
        if (Game1.activeClickableMenu == null)
        {
            Game1.activeClickableMenu = new GameMenu();
            return new ActionResult
            {
                Success = true,
                Message = "Opened menu",
                State = ActionState.Complete
            };
        }

        Game1.exitActiveMenu();
        return new ActionResult
        {
            Success = true,
            Message = "Closed menu",
            State = ActionState.Complete
        };
    }

    private ActionResult Cancel()
    {
        if (Game1.activeClickableMenu != null)
        {
            Game1.exitActiveMenu();
            return new ActionResult
            {
                Success = true,
                Message = "Canceled menu",
                State = ActionState.Complete
            };
        }

        return new ActionResult
        {
            Success = true,
            Message = "Nothing to cancel",
            State = ActionState.Complete
        };
    }

    private ActionResult DismissMenu()
    {
        var messages = new List<string>();

        // Handle active menu (dialogs, popups, level-up screens, shipping summary)
        if (Game1.activeClickableMenu != null)
        {
            var menuType = Game1.activeClickableMenu.GetType().Name;
            Game1.exitActiveMenu();
            messages.Add($"Dismissed {menuType}");
        }

        // Handle active event (cutscenes, festivals)
        if (Game1.eventUp && Game1.currentLocation?.currentEvent != null)
        {
            var evt = Game1.currentLocation.currentEvent;
            evt.skipEvent();
            messages.Add("Skipped event");
        }

        // Handle dialogue boxes
        if (Game1.dialogueUp)
        {
            Game1.dialogueUp = false;
            Game1.currentSpeaker = null;
            messages.Add("Dismissed dialogue");
        }

        // Handle pause menu
        if (Game1.paused)
        {
            Game1.paused = false;
            messages.Add("Unpaused");
        }

        if (messages.Count == 0)
        {
            return new ActionResult
            {
                Success = true,
                Message = "No menu/event to dismiss",
                State = ActionState.Complete
            };
        }

        return new ActionResult
        {
            Success = true,
            Message = string.Join(", ", messages),
            State = ActionState.Complete
        };
    }

    private ActionResult ConfirmDialog()
    {
        // Handle active events (cutscenes, pet adoption, character introductions)
        // Use skipEvent=false approach: simulate clicking to advance, don't skip
        if (Game1.eventUp && Game1.currentLocation?.currentEvent != null)
        {
            var evt = Game1.currentLocation.currentEvent;
            var playerPos = Game1.player.TilePoint;

            // Try to advance event by simulating action at player position
            // receiveActionPress(xTile, yTile) advances event dialogue
            evt.receiveActionPress(playerPos.X, playerPos.Y);
            return new ActionResult
            {
                Success = true,
                Message = "Advanced event",
                State = ActionState.Complete
            };
        }

        // Handle Yes/No dialogue boxes (like sleep confirmation, pet adoption question)
        if (Game1.activeClickableMenu is DialogueBox dialogueBox)
        {
            // Check if this is a question dialogue with responses
            if (dialogueBox.isQuestion && dialogueBox.responses != null && dialogueBox.responses.Length > 0)
            {
                // Select the first response (typically "Yes")
                var yesResponse = dialogueBox.responses[0];
                dialogueBox.selectedResponse = 0;
                Game1.currentLocation.answerDialogue(yesResponse);
                Game1.activeClickableMenu = null;

                return new ActionResult
                {
                    Success = true,
                    Message = $"Confirmed dialog: {yesResponse.responseText}",
                    State = ActionState.Complete
                };
            }
            else
            {
                // Regular dialogue box - advance/close it by simulating click
                dialogueBox.receiveLeftClick(0, 0);
                return new ActionResult
                {
                    Success = true,
                    Message = "Advanced dialogue",
                    State = ActionState.Complete
                };
            }
        }

        // Handle NPC dialogue (Game1.dialogueUp without menu)
        if (Game1.dialogueUp)
        {
            // Close dialogue by setting flags
            Game1.dialogueUp = false;
            Game1.currentSpeaker = null;
            return new ActionResult
            {
                Success = true,
                Message = "Dismissed dialogue",
                State = ActionState.Complete
            };
        }

        // No dialog/event to advance
        return new ActionResult
        {
            Success = true,
            Message = "No dialogue or event active",
            State = ActionState.Complete
        };
    }

    private ActionResult ToolbarNext()
    {
        Game1.player.shiftToolbar(true);
        return new ActionResult
        {
            Success = true,
            Message = "Toolbar next",
            State = ActionState.Complete
        };
    }

    private ActionResult ToolbarPrev()
    {
        Game1.player.shiftToolbar(false);
        return new ActionResult
        {
            Success = true,
            Message = "Toolbar previous",
            State = ActionState.Complete
        };
    }

    private ActionResult WarpTo(ActionTarget target)
    {
        if (target == null)
            return new ActionResult { Success = false, Error = "No target specified", State = ActionState.Failed };

        var player = Game1.player;

        // Stop any current movement
        player.Halt();
        player.forceCanMove();

        // Set position directly (tile * 64 = pixel position)
        player.Position = new Vector2(target.X * 64f, target.Y * 64f);

        _monitor.Log($"Warped {player.Name} to ({target.X}, {target.Y}) - pos now {player.Position}", LogLevel.Info);

        return new ActionResult
        {
            Success = true,
            Message = $"Warped to ({target.X}, {target.Y})",
            State = ActionState.Complete
        };
    }

    private ActionResult WarpToFarm()
    {
        // Warp to farm outside the farmhouse door
        Game1.warpFarmer("Farm", 64, 15, false);

        return new ActionResult
        {
            Success = true,
            Message = "Warped to Farm",
            State = ActionState.Complete
        };
    }

    private ActionResult WarpToHouse()
    {
        // Warp to inside the farmhouse
        Game1.warpFarmer("FarmHouse", 9, 9, false);

        return new ActionResult
        {
            Success = true,
            Message = "Warped to FarmHouse",
            State = ActionState.Complete
        };
    }

    private ActionResult GoToBed()
    {
        // Force the day to end and advance to next day
        var player = Game1.player;

        // Warp to farmhouse first
        if (Game1.currentLocation?.Name != "FarmHouse")
        {
            Game1.warpFarmer("FarmHouse", 9, 5, false);
        }

        // Mark player as in bed (for proper animation/saving)
        player.isInBed.Value = true;

        // Position at bed
        var farmHouse = Game1.getLocationFromName("FarmHouse") as StardewValley.Locations.FarmHouse;
        if (farmHouse != null)
        {
            var bedSpot = farmHouse.GetPlayerBedSpot();
            if (bedSpot != Microsoft.Xna.Framework.Point.Zero)
            {
                // Position at bed tile
                player.Position = new Microsoft.Xna.Framework.Vector2(bedSpot.X * 64f, bedSpot.Y * 64f);
            }
        }

        // Trigger the new day transition (0.0f = instant, no fade time)
        Game1.NewDay(0.0f);

        return new ActionResult
        {
            Success = true,
            Message = "Going to sleep - day will advance",
            State = ActionState.Complete
        };
    }

    // Default spawn points for common locations (for debug/testing)
    // Use case-insensitive comparer since Python sends lowercase location names
    private static readonly Dictionary<string, (int x, int y)> LocationSpawns = new(StringComparer.OrdinalIgnoreCase)
    {
        ["Farm"] = (64, 15),
        ["FarmHouse"] = (9, 9),
        ["Town"] = (43, 57),
        ["Beach"] = (20, 4),
        ["Mountain"] = (31, 20),
        ["Forest"] = (90, 16),
        ["BusStop"] = (22, 11),
        ["Mine"] = (13, 10),
        ["Desert"] = (35, 43),
        ["Woods"] = (8, 8),
        ["Backwoods"] = (14, 10),
        ["Railroad"] = (32, 40),
        ["SeedShop"] = (5, 20),  // Near door, not behind counter
        ["Saloon"] = (13, 18),
        ["Blacksmith"] = (3, 15),
        ["Hospital"] = (10, 19),
        ["ArchaeologyHouse"] = (3, 10),
        ["JoshHouse"] = (9, 22),
        ["HaleyHouse"] = (2, 5),
        ["SamHouse"] = (5, 23),
        ["Tent"] = (2, 5),
        ["AnimalShop"] = (12, 16),
        ["ScienceHouse"] = (6, 24),
        ["Greenhouse"] = (10, 22),
    };

    private ActionResult WarpToLocation(string locationName, ActionTarget target)
    {
        if (string.IsNullOrEmpty(locationName))
            return new ActionResult { Success = false, Error = "No location specified", State = ActionState.Failed };

        int x, y;

        // Use provided target coords, or fall back to known spawn point
        if (target != null && (target.X > 0 || target.Y > 0))
        {
            x = target.X;
            y = target.Y;
        }
        else if (LocationSpawns.TryGetValue(locationName, out var spawn))
        {
            x = spawn.x;
            y = spawn.y;
        }
        else
        {
            // Default fallback
            x = 10;
            y = 10;
        }

        try
        {
            Game1.warpFarmer(locationName, x, y, false);
            return new ActionResult
            {
                Success = true,
                Message = $"Warped to {locationName} ({x}, {y})",
                State = ActionState.Complete
            };
        }
        catch (Exception ex)
        {
            return new ActionResult
            {
                Success = false,
                Error = $"Failed to warp to {locationName}: {ex.Message}",
                State = ActionState.Failed
            };
        }
    }

    /// <summary>Reset executor state</summary>
    public void Reset()
    {
        _state = ActionState.Idle;
        _currentPath = null;
        _pathIndex = 0;
        _waitTicksRemaining = 0;
    }

    // =============================================================================
    // CRAFTING SYSTEM
    // =============================================================================

    private ActionResult CraftItem(string itemName, int quantity)
    {
        if (string.IsNullOrEmpty(itemName))
            return new ActionResult { Success = false, Error = "No item name specified", State = ActionState.Failed };

        var player = Game1.player;
        int qty = Math.Max(1, quantity);

        // Search for the recipe (case-insensitive)
        string recipeName = null;
        CraftingRecipe recipe = null;
        
        foreach (var knownRecipe in player.craftingRecipes.Keys)
        {
            if (knownRecipe.Equals(itemName, StringComparison.OrdinalIgnoreCase))
            {
                recipeName = knownRecipe;
                recipe = new CraftingRecipe(knownRecipe);
                break;
            }
        }

        // If not found by exact name, try partial match
        if (recipe == null)
        {
            foreach (var knownRecipe in player.craftingRecipes.Keys)
            {
                if (knownRecipe.Contains(itemName, StringComparison.OrdinalIgnoreCase))
                {
                    recipeName = knownRecipe;
                    recipe = new CraftingRecipe(knownRecipe);
                    break;
                }
            }
        }

        if (recipe == null)
        {
            var knownRecipes = string.Join(", ", player.craftingRecipes.Keys.Take(10));
            return new ActionResult
            {
                Success = false,
                Error = $"Recipe '{itemName}' not known. Known recipes: {knownRecipes}...",
                State = ActionState.Failed
            };
        }

        // Check if player has enough materials for requested quantity
        for (int i = 0; i < qty; i++)
        {
            if (!recipe.doesFarmerHaveIngredientsInInventory())
            {
                var needed = GetMissingIngredients(recipe, player);
                return new ActionResult
                {
                    Success = false,
                    Error = $"Missing ingredients for {recipeName}: {needed}",
                    State = ActionState.Failed
                };
            }

            // Consume ingredients and create item
            recipe.consumeIngredients(null); // null = use player inventory
            
            // Create the crafted item
            Item craftedItem = recipe.createItem();
            
            if (craftedItem == null)
            {
                return new ActionResult
                {
                    Success = false,
                    Error = $"Failed to create item for recipe {recipeName}",
                    State = ActionState.Failed
                };
            }

            // Add to inventory
            bool added = player.addItemToInventoryBool(craftedItem);
            if (!added)
            {
                // Try to drop on ground if inventory full
                Game1.createItemDebris(craftedItem, player.Position, player.FacingDirection, player.currentLocation);
                _monitor.Log($"Inventory full - dropped {craftedItem.DisplayName} on ground", LogLevel.Warn);
            }

            // Increment crafting count for achievements
            player.craftingRecipes[recipeName] += recipe.numberProducedPerCraft;
        }

        _monitor.Log($"Crafted {qty}x {recipeName}", LogLevel.Info);

        return new ActionResult
        {
            Success = true,
            Message = $"Crafted {qty}x {recipeName}",
            State = ActionState.Complete
        };
    }

    private string GetMissingIngredients(CraftingRecipe recipe, Farmer player)
    {
        var missing = new List<string>();
        
        foreach (var ingredient in recipe.recipeList)
        {
            string itemId = ingredient.Key;
            int needed = ingredient.Value;
            int have = 0;
            
            // Count how many the player has
            foreach (var item in player.Items)
            {
                if (item != null && (item.QualifiedItemId == itemId || item.ItemId == itemId))
                {
                    have += item.Stack;
                }
            }
            
            if (have < needed)
            {
                // Get display name for the item
                var sampleItem = ItemRegistry.Create(itemId);
                string displayName = sampleItem?.DisplayName ?? itemId;
                missing.Add($"{displayName} ({have}/{needed})");
            }
        }
        
        return string.Join(", ", missing);
    }

    // =============================================================================
    // ITEM PLACEMENT
    // =============================================================================

    private ActionResult PlaceItemAtTile(string direction)
    {
        var player = Game1.player;
        var activeObject = player.ActiveObject;

        if (activeObject == null)
        {
            return new ActionResult
            {
                Success = false,
                Error = "No placeable item selected",
                State = ActionState.Failed
            };
        }

        // Set facing direction if specified
        if (!string.IsNullOrEmpty(direction))
        {
            int facing = TilePathfinder.DirectionToFacing(direction);
            if (facing >= 0) player.FacingDirection = facing;
        }

        // Get tile in front of player
        var delta = GetDirectionDelta(player.FacingDirection);
        int targetX = player.TilePoint.X + delta.X;
        int targetY = player.TilePoint.Y + delta.Y;

        // Try to place the object
        bool success = Utility.tryToPlaceItem(player.currentLocation, activeObject, targetX * 64, targetY * 64);

        if (success)
        {
            _monitor.Log($"Placed {activeObject.DisplayName} at ({targetX}, {targetY})", LogLevel.Info);
            return new ActionResult
            {
                Success = true,
                Message = $"Placed {activeObject.DisplayName} at ({targetX}, {targetY})",
                State = ActionState.Complete
            };
        }
        else
        {
            return new ActionResult
            {
                Success = false,
                Error = $"Cannot place {activeObject.DisplayName} at ({targetX}, {targetY})",
                State = ActionState.Failed
            };
        }
    }

    // =============================================================================
    // CHEST & STORAGE SYSTEM
    // =============================================================================

    // Track the currently open chest for deposit/withdraw operations
    private StardewValley.Objects.Chest _currentOpenChest = null;

    private ActionResult OpenChest(string direction)
    {
        var player = Game1.player;
        var location = Game1.currentLocation;

        // Set facing direction if specified
        if (!string.IsNullOrEmpty(direction))
        {
            int facing = TilePathfinder.DirectionToFacing(direction);
            if (facing >= 0) player.FacingDirection = facing;
        }

        // Get tile in front of player
        var delta = GetDirectionDelta(player.FacingDirection);
        int targetX = player.TilePoint.X + delta.X;
        int targetY = player.TilePoint.Y + delta.Y;
        var targetTile = new Vector2(targetX, targetY);

        // Look for chest at target tile
        if (location.objects.TryGetValue(targetTile, out var obj) && obj is StardewValley.Objects.Chest chest)
        {
            _currentOpenChest = chest;
            
            // Get chest contents summary
            var contents = GetChestContentsSummary(chest);
            
            _monitor.Log($"Opened chest at ({targetX}, {targetY}): {contents}", LogLevel.Debug);
            
            return new ActionResult
            {
                Success = true,
                Message = $"Opened chest at ({targetX}, {targetY}). Contents: {contents}",
                State = ActionState.Complete
            };
        }

        return new ActionResult
        {
            Success = false,
            Error = $"No chest at ({targetX}, {targetY})",
            State = ActionState.Failed
        };
    }

    private ActionResult CloseChest()
    {
        if (_currentOpenChest == null)
        {
            return new ActionResult
            {
                Success = true,
                Message = "No chest was open",
                State = ActionState.Complete
            };
        }

        _currentOpenChest = null;
        
        return new ActionResult
        {
            Success = true,
            Message = "Closed chest",
            State = ActionState.Complete
        };
    }

    private ActionResult DepositItem(int slot, int quantity)
    {
        if (_currentOpenChest == null)
        {
            return new ActionResult
            {
                Success = false,
                Error = "No chest is open. Use open_chest first.",
                State = ActionState.Failed
            };
        }

        var player = Game1.player;
        
        // Validate slot
        if (slot < 0 || slot >= player.Items.Count)
        {
            return new ActionResult
            {
                Success = false,
                Error = $"Invalid slot: {slot}",
                State = ActionState.Failed
            };
        }

        var item = player.Items[slot];
        if (item == null)
        {
            return new ActionResult
            {
                Success = false,
                Error = $"Slot {slot} is empty",
                State = ActionState.Failed
            };
        }

        // Determine quantity to deposit (-1 = entire stack)
        int depositQty = quantity <= 0 ? item.Stack : Math.Min(quantity, item.Stack);
        string itemName = item.DisplayName;

        // Create item to deposit
        Item toDeposit;
        if (depositQty >= item.Stack)
        {
            // Moving entire stack
            toDeposit = item;
            player.Items[slot] = null;
        }
        else
        {
            // Splitting stack
            toDeposit = item.getOne();
            toDeposit.Stack = depositQty;
            item.Stack -= depositQty;
        }

        // Add to chest
        Item remaining = _currentOpenChest.addItem(toDeposit);
        
        if (remaining != null)
        {
            // Chest couldn't accept all items, return remainder to player
            player.addItemToInventory(remaining);
            int actualDeposited = depositQty - remaining.Stack;
            
            if (actualDeposited > 0)
            {
                return new ActionResult
                {
                    Success = true,
                    Message = $"Deposited {actualDeposited}x {itemName} (chest partially full)",
                    State = ActionState.Complete
                };
            }
            else
            {
                return new ActionResult
                {
                    Success = false,
                    Error = "Chest is full",
                    State = ActionState.Failed
                };
            }
        }

        _monitor.Log($"Deposited {depositQty}x {itemName} to chest", LogLevel.Debug);
        
        return new ActionResult
        {
            Success = true,
            Message = $"Deposited {depositQty}x {itemName}",
            State = ActionState.Complete
        };
    }

    private ActionResult WithdrawItem(int slot, int quantity)
    {
        if (_currentOpenChest == null)
        {
            return new ActionResult
            {
                Success = false,
                Error = "No chest is open. Use open_chest first.",
                State = ActionState.Failed
            };
        }

        var player = Game1.player;
        var chestItems = _currentOpenChest.Items;
        
        // Validate slot
        if (slot < 0 || slot >= chestItems.Count)
        {
            return new ActionResult
            {
                Success = false,
                Error = $"Invalid chest slot: {slot}. Chest has {chestItems.Count} slots.",
                State = ActionState.Failed
            };
        }

        var item = chestItems[slot];
        if (item == null)
        {
            return new ActionResult
            {
                Success = false,
                Error = $"Chest slot {slot} is empty",
                State = ActionState.Failed
            };
        }

        // Determine quantity to withdraw (-1 = entire stack)
        int withdrawQty = quantity <= 0 ? item.Stack : Math.Min(quantity, item.Stack);
        string itemName = item.DisplayName;

        // Create item to withdraw
        Item toWithdraw;
        if (withdrawQty >= item.Stack)
        {
            // Taking entire stack
            toWithdraw = item;
            chestItems[slot] = null;
        }
        else
        {
            // Splitting stack
            toWithdraw = item.getOne();
            toWithdraw.Stack = withdrawQty;
            item.Stack -= withdrawQty;
        }

        // Add to player inventory
        bool added = player.addItemToInventoryBool(toWithdraw);
        
        if (!added)
        {
            // Return to chest if player inventory full
            _currentOpenChest.addItem(toWithdraw);
            return new ActionResult
            {
                Success = false,
                Error = "Player inventory is full",
                State = ActionState.Failed
            };
        }

        _monitor.Log($"Withdrew {withdrawQty}x {itemName} from chest", LogLevel.Debug);
        
        return new ActionResult
        {
            Success = true,
            Message = $"Withdrew {withdrawQty}x {itemName}",
            State = ActionState.Complete
        };
    }

    private string GetChestContentsSummary(StardewValley.Objects.Chest chest)
    {
        var items = chest.Items.Where(i => i != null).ToList();
        
        if (items.Count == 0)
            return "empty";

        var summary = items
            .GroupBy(i => i.DisplayName)
            .Select(g => $"{g.Sum(i => i.Stack)}x {g.Key}")
            .Take(5);  // Limit to 5 item types for brevity
        
        string result = string.Join(", ", summary);
        if (items.Count > 5)
            result += $" (+{items.Count - 5} more types)";
        
        return result;
    }

    // =============================================================================
    // SESSION 125: FISHING ACTIONS
    // =============================================================================

    private ActionResult CastFishingRod(string direction)
    {
        var player = Game1.player;

        // Set facing direction
        if (!string.IsNullOrEmpty(direction))
        {
            int facing = TilePathfinder.DirectionToFacing(direction);
            if (facing >= 0) player.FacingDirection = facing;
        }

        // Check if holding fishing rod
        if (player.CurrentTool is not StardewValley.Tools.FishingRod rod)
        {
            return new ActionResult
            {
                Success = false,
                Error = "No fishing rod equipped. Use select_item_type with 'Fishing Rod'.",
                State = ActionState.Failed
            };
        }

        // Start fishing
        player.BeginUsingTool();

        return new ActionResult
        {
            Success = true,
            Message = "Cast fishing rod",
            State = ActionState.PerformingAction
        };
    }

    private ActionResult StartFishing()
    {
        var player = Game1.player;
        var location = player.currentLocation;

        // Equip fishing rod if not equipped
        for (int i = 0; i < player.Items.Count; i++)
        {
            if (player.Items[i] is StardewValley.Tools.FishingRod)
            {
                player.CurrentToolIndex = i;
                break;
            }
        }

        if (player.CurrentTool is not StardewValley.Tools.FishingRod rod)
        {
            return new ActionResult
            {
                Success = false,
                Error = "No fishing rod in inventory",
                State = ActionState.Failed
            };
        }

        // Face water (find nearest water tile)
        var playerTile = player.TilePoint;
        int[] directions = { 0, 2, 1, 3 }; // Check down, up, right, left
        foreach (int dir in directions)
        {
            var delta = GetDirectionDelta(dir);
            var checkTile = new Point(playerTile.X + delta.X, playerTile.Y + delta.Y);
            if (location.isWaterTile(checkTile.X, checkTile.Y))
            {
                player.FacingDirection = dir;
                break;
            }
        }

        // Start fishing
        player.BeginUsingTool();

        return new ActionResult
        {
            Success = true,
            Message = "Started fishing",
            State = ActionState.PerformingAction
        };
    }

    // =============================================================================
    // SESSION 125: ANIMAL ACTIONS
    // =============================================================================

    private ActionResult PetAnimal(string direction)
    {
        var player = Game1.player;
        var location = player.currentLocation;

        // Set facing direction
        if (!string.IsNullOrEmpty(direction))
        {
            int facing = TilePathfinder.DirectionToFacing(direction);
            if (facing >= 0) player.FacingDirection = facing;
        }

        // Find animal at facing tile
        var delta = GetDirectionDelta(player.FacingDirection);
        var targetTile = new Vector2(player.TilePoint.X + delta.X, player.TilePoint.Y + delta.Y);
        var targetRect = new Microsoft.Xna.Framework.Rectangle((int)targetTile.X * 64, (int)targetTile.Y * 64, 64, 64);

        foreach (var animal in location.animals.Values)
        {
            if (animal.GetBoundingBox().Intersects(targetRect))
            {
                // Pet the animal
                animal.pet(player);

                return new ActionResult
                {
                    Success = true,
                    Message = $"Petted {animal.displayName}",
                    State = ActionState.Complete
                };
            }
        }

        return new ActionResult
        {
            Success = false,
            Error = "No animal found in that direction",
            State = ActionState.Failed
        };
    }

    private ActionResult MilkAnimal(string direction)
    {
        var player = Game1.player;
        var location = player.currentLocation;

        // Set facing direction
        if (!string.IsNullOrEmpty(direction))
        {
            int facing = TilePathfinder.DirectionToFacing(direction);
            if (facing >= 0) player.FacingDirection = facing;
        }

        // Session 126: Verify there's a milkable animal in range first
        var delta = GetDirectionDelta(player.FacingDirection);
        var targetTile = new Vector2(player.TilePoint.X + delta.X, player.TilePoint.Y + delta.Y);
        var targetRect = new Microsoft.Xna.Framework.Rectangle((int)targetTile.X * 64, (int)targetTile.Y * 64, 64, 64);

        StardewValley.FarmAnimal targetAnimal = null;
        foreach (var animal in location.animals.Values)
        {
            if (animal.GetBoundingBox().Intersects(targetRect))
            {
                // Check if milkable (cow or goat that hasn't been milked today)
                string type = animal.type.Value.ToLower();
                if ((type.Contains("cow") || type.Contains("goat")) && !animal.wasPet.Value)
                {
                    targetAnimal = animal;
                    break;
                }
            }
        }

        if (targetAnimal == null)
        {
            return new ActionResult
            {
                Success = false,
                Error = "No milkable animal found in that direction",
                State = ActionState.Failed
            };
        }

        // Equip milk pail
        for (int i = 0; i < player.Items.Count; i++)
        {
            if (player.Items[i] is StardewValley.Tools.MilkPail)
            {
                player.CurrentToolIndex = i;
                break;
            }
        }

        if (player.CurrentTool is not StardewValley.Tools.MilkPail)
        {
            return new ActionResult
            {
                Success = false,
                Error = "No milk pail in inventory",
                State = ActionState.Failed
            };
        }

        player.BeginUsingTool();

        return new ActionResult
        {
            Success = true,
            Message = $"Milking {targetAnimal.displayName}",
            State = ActionState.PerformingAction
        };
    }

    private ActionResult ShearAnimal(string direction)
    {
        var player = Game1.player;
        var location = player.currentLocation;

        // Set facing direction
        if (!string.IsNullOrEmpty(direction))
        {
            int facing = TilePathfinder.DirectionToFacing(direction);
            if (facing >= 0) player.FacingDirection = facing;
        }

        // Session 126: Verify there's a shearable animal in range first
        var delta = GetDirectionDelta(player.FacingDirection);
        var targetTile = new Vector2(player.TilePoint.X + delta.X, player.TilePoint.Y + delta.Y);
        var targetRect = new Microsoft.Xna.Framework.Rectangle((int)targetTile.X * 64, (int)targetTile.Y * 64, 64, 64);

        StardewValley.FarmAnimal targetAnimal = null;
        foreach (var animal in location.animals.Values)
        {
            if (animal.GetBoundingBox().Intersects(targetRect))
            {
                // Check if shearable (sheep or rabbit with wool ready)
                string type = animal.type.Value.ToLower();
                if ((type.Contains("sheep") || type.Contains("rabbit")) && animal.currentProduce.Value != null)
                {
                    targetAnimal = animal;
                    break;
                }
            }
        }

        if (targetAnimal == null)
        {
            return new ActionResult
            {
                Success = false,
                Error = "No shearable animal found in that direction",
                State = ActionState.Failed
            };
        }

        // Equip shears
        for (int i = 0; i < player.Items.Count; i++)
        {
            if (player.Items[i] is StardewValley.Tools.Shears)
            {
                player.CurrentToolIndex = i;
                break;
            }
        }

        if (player.CurrentTool is not StardewValley.Tools.Shears)
        {
            return new ActionResult
            {
                Success = false,
                Error = "No shears in inventory",
                State = ActionState.Failed
            };
        }

        player.BeginUsingTool();

        return new ActionResult
        {
            Success = true,
            Message = $"Shearing {targetAnimal.displayName}",
            State = ActionState.PerformingAction
        };
    }

    private ActionResult CollectAnimalProduct(string direction)
    {
        var player = Game1.player;
        var location = player.currentLocation;

        // Set facing direction
        if (!string.IsNullOrEmpty(direction))
        {
            int facing = TilePathfinder.DirectionToFacing(direction);
            if (facing >= 0) player.FacingDirection = facing;
        }

        // Check for items on ground (eggs, truffles, etc.)
        var delta = GetDirectionDelta(player.FacingDirection);
        var targetTile = new Vector2(player.TilePoint.X + delta.X, player.TilePoint.Y + delta.Y);

        if (location.Objects.TryGetValue(targetTile, out var obj))
        {
            // Try to pick up
            if (player.addItemToInventoryBool(obj))
            {
                location.Objects.Remove(targetTile);
                return new ActionResult
                {
                    Success = true,
                    Message = $"Collected {obj.DisplayName}",
                    State = ActionState.Complete
                };
            }
            else
            {
                return new ActionResult
                {
                    Success = false,
                    Error = "Inventory full",
                    State = ActionState.Failed
                };
            }
        }

        return new ActionResult
        {
            Success = false,
            Error = "No item to collect at that tile",
            State = ActionState.Failed
        };
    }

    // =============================================================================
    // SESSION 125: FORAGING ACTIONS
    // =============================================================================

    private ActionResult ShakeTree(string direction)
    {
        var player = Game1.player;
        var location = player.currentLocation;

        // Set facing direction
        if (!string.IsNullOrEmpty(direction))
        {
            int facing = TilePathfinder.DirectionToFacing(direction);
            if (facing >= 0) player.FacingDirection = facing;
        }

        var delta = GetDirectionDelta(player.FacingDirection);
        var targetTile = new Vector2(player.TilePoint.X + delta.X, player.TilePoint.Y + delta.Y);

        // Check for tree at target tile
        if (location.terrainFeatures.TryGetValue(targetTile, out var feature))
        {
            if (feature is StardewValley.TerrainFeatures.Tree tree)
            {
                // Shake the tree
                tree.performUseAction(targetTile);

                return new ActionResult
                {
                    Success = true,
                    Message = "Shook tree",
                    State = ActionState.Complete
                };
            }
            else if (feature is StardewValley.TerrainFeatures.FruitTree fruitTree)
            {
                // Shake fruit tree
                fruitTree.performUseAction(targetTile);

                return new ActionResult
                {
                    Success = true,
                    Message = "Shook fruit tree",
                    State = ActionState.Complete
                };
            }
        }

        return new ActionResult
        {
            Success = false,
            Error = "No tree found in that direction",
            State = ActionState.Failed
        };
    }

    private ActionResult DigArtifactSpot(string direction)
    {
        var player = Game1.player;
        var location = player.currentLocation;

        // Set facing direction
        if (!string.IsNullOrEmpty(direction))
        {
            int facing = TilePathfinder.DirectionToFacing(direction);
            if (facing >= 0) player.FacingDirection = facing;
        }

        // Equip hoe
        for (int i = 0; i < player.Items.Count; i++)
        {
            if (player.Items[i] is Hoe)
            {
                player.CurrentToolIndex = i;
                break;
            }
        }

        if (player.CurrentTool is not Hoe)
        {
            return new ActionResult
            {
                Success = false,
                Error = "No hoe in inventory",
                State = ActionState.Failed
            };
        }

        // Use tool (hoe will reveal artifact if spot exists)
        player.BeginUsingTool();

        return new ActionResult
        {
            Success = true,
            Message = "Digging artifact spot",
            State = ActionState.PerformingAction
        };
    }

    // =============================================================================
    // SESSION 125: RELIABLE MINE DESCENT
    // =============================================================================

    private ActionResult DescendMine()
    {
        var player = Game1.player;
        var location = player.currentLocation;

        // If not in mines, warp there first
        if (location?.Name != "Mine" && location is not MineShaft)
        {
            Game1.warpFarmer("Mine", 13, 10, false);
            return new ActionResult
            {
                Success = true,
                Message = "Warped to mine entrance - call descend_mine again to enter level 1",
                State = ActionState.Complete
            };
        }

        // Get current level
        int currentLevel = 0;
        if (location is MineShaft mine)
        {
            currentLevel = mine.mineLevel;
        }

        // Enter next level
        int nextLevel = currentLevel + 1;

        // Skull Cavern starts at 121
        if (location?.Name == "SkullCave" || (location is MineShaft ms && ms.mineLevel >= 121))
        {
            nextLevel = Math.Max(121, currentLevel + 1);
        }

        _monitor.Log($"DescendMine: From level {currentLevel} to level {nextLevel}", LogLevel.Info);
        Game1.enterMine(nextLevel);

        return new ActionResult
        {
            Success = true,
            Message = $"Descended from level {currentLevel} to level {nextLevel}",
            State = ActionState.Complete
        };
    }
}
