using Microsoft.Xna.Framework;
using StardewAI.GameBridge.Models;
using StardewAI.GameBridge.Pathfinding;
using StardewModdingAPI;
using StardewValley;
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
                "move_direction" => MoveDirection(command.Direction, command.Tiles),
                "warp" => WarpTo(command.Target),
                "warp_to_farm" => WarpToFarm(),
                "warp_to_house" => WarpToHouse(),
                "go_to_bed" => GoToBed(),
                "warp_location" => WarpToLocation(command.Location, command.Target),
                "use_tool" => UseTool(command.Direction),
                "equip_tool" => EquipTool(command.Tool),
                "select_slot" => SelectSlot(command.Slot),
                "interact" => Interact(command.Target),
                "interact_facing" => InteractFacing(),
                "harvest" => Harvest(command.Direction),
                "ship" => ShipItem(command.Slot),
                "eat" => EatItem(command.Slot),
                "buy" => BuyItem(command.Item, command.Quantity),
                "wait" => Wait(command.Ticks),
                "face" => Face(command.Direction),
                "toggle_menu" => ToggleMenu(),
                "cancel" => Cancel(),
                "toolbar_next" => ToolbarNext(),
                "toolbar_prev" => ToolbarPrev(),
                "dismiss_menu" => DismissMenu(),
                "confirm_dialog" => ConfirmDialog(),
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

        var start = Game1.player.TilePoint;
        var end = new Point(target.X, target.Y);

        _currentPath = _pathfinder.FindPath(start, end, Game1.currentLocation);

        if (_currentPath == null || _currentPath.Count == 0)
        {
            return new ActionResult { Success = false, Error = $"No path found to ({target.X}, {target.Y})", State = ActionState.Failed };
        }

        _pathIndex = 0;
        _state = ActionState.MovingToTarget;

        return new ActionResult
        {
            Success = true,
            Message = $"Moving to ({target.X}, {target.Y}), {_currentPath.Count} tiles",
            State = ActionState.MovingToTarget
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
        // Handle Yes/No dialogue boxes (like sleep confirmation)
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
                // Regular dialogue box - just close it
                Game1.activeClickableMenu = null;
                return new ActionResult
                {
                    Success = true,
                    Message = "Closed dialogue (no responses)",
                    State = ActionState.Complete
                };
            }
        }

        // No dialog to confirm
        return new ActionResult
        {
            Success = false,
            Error = "No dialogue box active",
            State = ActionState.Failed
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
}
