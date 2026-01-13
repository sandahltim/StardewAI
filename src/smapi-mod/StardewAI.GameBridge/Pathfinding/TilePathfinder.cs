using Microsoft.Xna.Framework;
using StardewValley;

namespace StardewAI.GameBridge.Pathfinding;

/// <summary>
/// A* pathfinding for tile-based movement.
/// Finds shortest path avoiding obstacles, NPCs, and buildings.
/// </summary>
public class TilePathfinder
{
    private class Node
    {
        public Point Position { get; init; }
        public int G { get; set; }
        public int H { get; init; }
        public Node Parent { get; init; }
        public int F => G + H;
    }

    /// <summary>Find path from start to end tile in current location</summary>
    public List<Point> FindPath(Point start, Point end, GameLocation location, int maxSearchTiles = 500)
    {
        if (start == end) return new List<Point> { start };

        var openSet = new PriorityQueue<Node, int>();
        var closedSet = new HashSet<Point>();
        var gScores = new Dictionary<Point, int>();

        var startNode = new Node { Position = start, G = 0, H = Heuristic(start, end), Parent = null };
        openSet.Enqueue(startNode, startNode.F);
        gScores[start] = 0;

        int searchedTiles = 0;

        while (openSet.Count > 0 && searchedTiles < maxSearchTiles)
        {
            var current = openSet.Dequeue();
            searchedTiles++;

            if (current.Position == end)
            {
                return ReconstructPath(current);
            }

            if (closedSet.Contains(current.Position))
                continue;

            closedSet.Add(current.Position);

            // Check all 4 cardinal neighbors
            foreach (var neighbor in GetNeighbors(current.Position))
            {
                if (closedSet.Contains(neighbor))
                    continue;

                if (!IsTilePassable(neighbor, location))
                    continue;

                int tentativeG = current.G + 1;

                if (!gScores.TryGetValue(neighbor, out int existingG) || tentativeG < existingG)
                {
                    gScores[neighbor] = tentativeG;
                    var neighborNode = new Node { Position = neighbor, G = tentativeG, H = Heuristic(neighbor, end), Parent = current };
                    openSet.Enqueue(neighborNode, neighborNode.F);
                }
            }
        }

        // No path found
        return null;
    }

    /// <summary>Check if a tile is passable</summary>
    public bool IsTilePassable(Point tile, GameLocation location)
    {
        // Check bounds
        if (tile.X < 0 || tile.Y < 0)
            return false;

        // Check map bounds
        if (location.Map != null)
        {
            var layer = location.Map.GetLayer("Back");
            if (layer != null && (tile.X >= layer.LayerWidth || tile.Y >= layer.LayerHeight))
                return false;
        }

        // Use game's built-in passability check
        var tileLocation = new Vector2(tile.X, tile.Y);

        // Check if tile is blocked
        if (!location.isTilePassable(new xTile.Dimensions.Location(tile.X, tile.Y), Game1.viewport))
            return false;

        // Check for objects blocking
        if (location.objects.TryGetValue(tileLocation, out var obj) && !obj.isPassable())
            return false;

        // Check for ResourceClumps (large stumps, logs, boulders - 2x2 obstacles)
        // These are solid and need upgraded tools to clear
        foreach (var clump in location.resourceClumps)
        {
            // ResourceClumps occupy multiple tiles (usually 2x2)
            if (tile.X >= clump.Tile.X && tile.X < clump.Tile.X + clump.width.Value &&
                tile.Y >= clump.Tile.Y && tile.Y < clump.Tile.Y + clump.height.Value)
            {
                return false;
            }
        }

        // Check for NPCs (we can path through them but might want to avoid)
        // Leaving NPCs passable for now - player can push through

        return true;
    }

    private static int Heuristic(Point a, Point b)
    {
        // Manhattan distance
        return Math.Abs(a.X - b.X) + Math.Abs(a.Y - b.Y);
    }

    private static IEnumerable<Point> GetNeighbors(Point p)
    {
        yield return new Point(p.X, p.Y - 1); // Up
        yield return new Point(p.X + 1, p.Y); // Right
        yield return new Point(p.X, p.Y + 1); // Down
        yield return new Point(p.X - 1, p.Y); // Left
    }

    private static List<Point> ReconstructPath(Node endNode)
    {
        var path = new List<Point>();
        var current = endNode;

        while (current != null)
        {
            path.Add(current.Position);
            current = current.Parent;
        }

        path.Reverse();
        return path;
    }

    /// <summary>Convert direction string to facing direction int</summary>
    /// <remarks>
    /// Accepts both screen-relative (up/down/left/right) and cardinal (north/south/east/west).
    /// Cardinal is preferred for clarity:
    ///   north=0 (screen up), east=1 (screen right), south=2 (screen down), west=3 (screen left)
    /// </remarks>
    public static int DirectionToFacing(string direction)
    {
        return direction?.ToLower() switch
        {
            // Cardinal directions (preferred - unambiguous)
            "north" => 0,
            "east" => 1,
            "south" => 2,
            "west" => 3,
            // Screen-relative (legacy support)
            "up" => 0,
            "right" => 1,
            "down" => 2,
            "left" => 3,
            _ => -1
        };
    }

    /// <summary>Convert facing direction int to cardinal direction string</summary>
    public static string FacingToCardinal(int facing)
    {
        return facing switch
        {
            0 => "north",
            1 => "east",
            2 => "south",
            3 => "west",
            _ => "unknown"
        };
    }

    /// <summary>Get direction from one tile to an adjacent tile</summary>
    public static int GetDirectionBetweenTiles(Point from, Point to)
    {
        int dx = to.X - from.X;
        int dy = to.Y - from.Y;

        if (dy < 0) return 0; // Up
        if (dx > 0) return 1; // Right
        if (dy > 0) return 2; // Down
        if (dx < 0) return 3; // Left

        return 2; // Default down
    }
}
