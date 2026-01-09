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
                "wait" => Wait(command.Ticks),
                "face" => Face(command.Direction),
                "toggle_menu" => ToggleMenu(),
                "cancel" => Cancel(),
                "toolbar_next" => ToolbarNext(),
                "toolbar_prev" => ToolbarPrev(),
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
                // Snap to final tile center for consistent tool usage
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

        // Build path, checking passability for each tile
        _currentPath = new List<Point> { start };
        for (int i = 1; i <= tiles; i++)
        {
            var nextTile = new Point(start.X + delta.X * i, start.Y + delta.Y * i);
            var tileLocation = new xTile.Dimensions.Location(nextTile.X, nextTile.Y);

            // Check if tile is passable
            if (!location.isTilePassable(tileLocation, Game1.viewport))
            {
                _monitor.Log($"Tile ({nextTile.X}, {nextTile.Y}) is blocked, stopping path", LogLevel.Debug);
                break;
            }
            _currentPath.Add(nextTile);
        }

        int actualTiles = _currentPath.Count - 1;
        if (actualTiles == 0)
        {
            _state = ActionState.Complete;
            return new ActionResult
            {
                Success = false,
                Error = $"Path blocked - cannot move {direction}",
                State = ActionState.Failed
            };
        }

        _pathIndex = 1; // Skip current position
        _state = ActionState.MovingToTarget;

        return new ActionResult
        {
            Success = true,
            Message = $"Moving {direction} {actualTiles} tiles",
            State = ActionState.MovingToTarget
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

        // Check if we've reached the target tile - snap to center for consistency
        if (currentTile.X == targetTile.X && currentTile.Y == targetTile.Y)
        {
            // Snap to tile center to prevent tool misalignment from edge positions
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
                // Remove from inventory if placed
                if (activeObject.Stack <= 1)
                    player.removeItemFromInventory(activeObject);
                else
                    activeObject.Stack--;

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
        // Warp to farmhouse bed position and trigger sleep dialog
        var player = Game1.player;

        // First, ensure we're in the farmhouse
        if (Game1.currentLocation?.Name != "FarmHouse")
        {
            Game1.warpFarmer("FarmHouse", 9, 5, false);
        }
        else
        {
            // Already in farmhouse, move to bed
            player.Position = new Microsoft.Xna.Framework.Vector2(9 * 64f, 5 * 64f);
        }

        // Face up toward bed
        player.FacingDirection = 0;

        // Try to find and interact with the bed
        var farmHouse = Game1.getLocationFromName("FarmHouse") as StardewValley.Locations.FarmHouse;
        if (farmHouse != null)
        {
            var bedSpot = farmHouse.GetPlayerBedSpot();
            if (bedSpot != Microsoft.Xna.Framework.Point.Zero)
            {
                // Position player at bed
                player.Position = new Microsoft.Xna.Framework.Vector2(bedSpot.X * 64f, bedSpot.Y * 64f);
                player.FacingDirection = 0;

                // Trigger the bed interaction - this shows the sleep dialog
                farmHouse.answerDialogueAction("Sleep_Yes", null);

                return new ActionResult
                {
                    Success = true,
                    Message = $"Going to bed at ({bedSpot.X}, {bedSpot.Y})",
                    State = ActionState.Complete
                };
            }
        }

        return new ActionResult
        {
            Success = true,
            Message = "Positioned near bed - interact to sleep",
            State = ActionState.Complete
        };
    }

    // Default spawn points for common locations (for debug/testing)
    private static readonly Dictionary<string, (int x, int y)> LocationSpawns = new()
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
        ["SeedShop"] = (4, 19),
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
