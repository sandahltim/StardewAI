using StardewAI.GameBridge.Models;
using StardewModdingAPI;
using StardewModdingAPI.Events;
using StardewValley;
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
    private volatile SurroundingsState _cachedSurroundings;
    private volatile FarmState _cachedFarmState;

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

        // Start HTTP server
        _httpServer = new HttpServer(HttpPort, Monitor);
        _httpServer.GetGameState = () => _cachedState;
        _httpServer.GetSurroundings = () => _cachedSurroundings;
        _httpServer.GetFarmState = () => _cachedFarmState;
        _httpServer.QueueAction = QueueActionFromHttp;
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

    protected override void Dispose(bool disposing)
    {
        if (disposing)
        {
            _httpServer?.Dispose();
        }
        base.Dispose(disposing);
    }
}
