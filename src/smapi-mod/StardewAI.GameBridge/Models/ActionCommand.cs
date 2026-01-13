namespace StardewAI.GameBridge.Models;

/// <summary>Action command from AI agent</summary>
public class ActionCommand
{
    public string Action { get; set; }
    public ActionTarget Target { get; set; }
    public string Direction { get; set; }
    public int Tiles { get; set; }
    public string Tool { get; set; }
    public string Seed { get; set; }
    public int Slot { get; set; }
    public int Ticks { get; set; }
    public string Location { get; set; }  // For warp_location action
    public string Item { get; set; }      // For buy action - item name or ID
    public int Quantity { get; set; } = 1; // For buy action - how many to buy
    public string ItemType { get; set; }  // For select_item_type - category like "seed", "crop", "food"
}

/// <summary>Target tile coordinates</summary>
public class ActionTarget
{
    public int X { get; set; }
    public int Y { get; set; }
}

/// <summary>Result of an action execution</summary>
public class ActionResult
{
    public bool Success { get; set; }
    public string Message { get; set; }
    public string Error { get; set; }
    public ActionState State { get; set; }
}

/// <summary>Current action execution state</summary>
public enum ActionState
{
    Idle,
    MovingToTarget,
    PerformingAction,
    WaitingForAnimation,
    Complete,
    Failed
}

/// <summary>API response wrapper</summary>
public class ApiResponse<T>
{
    public bool Success { get; set; }
    public T Data { get; set; }
    public string Error { get; set; }

    public static ApiResponse<T> Ok(T data) => new() { Success = true, Data = data };
    public static ApiResponse<T> Fail(string error) => new() { Success = false, Error = error };
}

/// <summary>Health check response</summary>
public class HealthCheck
{
    public string Status { get; set; }
    public bool GameRunning { get; set; }
    public bool PlayerInGame { get; set; }
    public string ModVersion { get; set; }
}
