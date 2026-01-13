using System.Net;
using System.Text;
using System.Text.Json;
using StardewAI.GameBridge.Models;
using StardewModdingAPI;

namespace StardewAI.GameBridge;

/// <summary>
/// Embedded HTTP server for AI agent communication.
/// Runs on a background thread, interacts with game via thread-safe queues.
/// </summary>
public class HttpServer : IDisposable
{
    private readonly HttpListener _listener;
    private readonly IMonitor _monitor;
    private readonly int _port;
    private Thread _listenerThread;
    private volatile bool _running;

    // Callbacks set by ModEntry to access game thread safely
    public Func<GameState> GetGameState { get; set; }
    public Func<ActionCommand, ActionResult> QueueAction { get; set; }
    public Func<SurroundingsState> GetSurroundings { get; set; }
    public Func<FarmState> GetFarmState { get; set; }

    // Pathfinding callbacks
    public Func<int, int, int, int, PathCheckResult> CheckPath { get; set; }
    public Func<int, int, PassableResult> CheckPassable { get; set; }
    public Func<int, int, int, PassableAreaResult> CheckPassableArea { get; set; }
    public Func<SkillsState> GetSkills { get; set; }

    // Game data callbacks
    public Func<NpcsState> GetNpcs { get; set; }
    public Func<AnimalsState> GetAnimals { get; set; }
    public Func<MachinesState> GetMachines { get; set; }
    public Func<CalendarState> GetCalendar { get; set; }
    public Func<FishingState> GetFishing { get; set; }
    public Func<MiningState> GetMining { get; set; }
    public Func<StorageState> GetStorage { get; set; }

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        WriteIndented = false
    };

    public HttpServer(int port, IMonitor monitor)
    {
        _port = port;
        _monitor = monitor;
        _listener = new HttpListener();
        _listener.Prefixes.Add($"http://localhost:{port}/");
        _listener.Prefixes.Add($"http://127.0.0.1:{port}/");
    }

    public void Start()
    {
        if (_running) return;

        try
        {
            _listener.Start();
            _running = true;
            _listenerThread = new Thread(ListenLoop) { IsBackground = true };
            _listenerThread.Start();
            _monitor.Log($"GameBridge HTTP server started on port {_port}", LogLevel.Info);
        }
        catch (Exception ex)
        {
            _monitor.Log($"Failed to start HTTP server: {ex.Message}", LogLevel.Error);
        }
    }

    public void Stop()
    {
        _running = false;
        _listener.Stop();
        _monitor.Log("GameBridge HTTP server stopped", LogLevel.Info);
    }

    private void ListenLoop()
    {
        while (_running)
        {
            try
            {
                var context = _listener.GetContext();
                ThreadPool.QueueUserWorkItem(_ => HandleRequest(context));
            }
            catch (HttpListenerException) when (!_running)
            {
                // Expected when stopping
            }
            catch (Exception ex)
            {
                _monitor.Log($"HTTP listener error: {ex.Message}", LogLevel.Error);
            }
        }
    }

    private void HandleRequest(HttpListenerContext context)
    {
        var request = context.Request;
        var response = context.Response;

        try
        {
            string path = request.Url?.AbsolutePath ?? "/";
            string method = request.HttpMethod;

            _monitor.Log($"Request: {method} {path}", LogLevel.Trace);

            string responseJson = (method, path) switch
            {
                ("GET", "/health") => HandleHealth(),
                ("GET", "/state") => HandleGetState(),
                ("GET", "/surroundings") => HandleGetSurroundings(),
                ("GET", "/farm") => HandleGetFarm(),
                ("POST", "/action") => HandleAction(request),
                // Pathfinding & navigation
                ("GET", "/check-path") => HandleCheckPath(request),
                ("GET", "/passable") => HandlePassable(request),
                ("GET", "/passable-area") => HandlePassableArea(request),
                // Player data
                ("GET", "/skills") => HandleGetSkills(),
                // Game world data
                ("GET", "/npcs") => HandleGetNpcs(),
                ("GET", "/animals") => HandleGetAnimals(),
                ("GET", "/machines") => HandleGetMachines(),
                ("GET", "/calendar") => HandleGetCalendar(),
                ("GET", "/fishing") => HandleGetFishing(),
                ("GET", "/mining") => HandleGetMining(),
                ("GET", "/storage") => HandleGetStorage(),
                _ => JsonSerializer.Serialize(ApiResponse<object>.Fail($"Unknown endpoint: {method} {path}"), JsonOptions)
            };

            SendResponse(response, responseJson);
        }
        catch (Exception ex)
        {
            _monitor.Log($"Request error: {ex.Message}", LogLevel.Error);
            SendResponse(response, JsonSerializer.Serialize(ApiResponse<object>.Fail(ex.Message), JsonOptions), 500);
        }
    }

    private string HandleHealth()
    {
        var health = new HealthCheck
        {
            Status = "ok",
            GameRunning = true,
            PlayerInGame = GetGameState?.Invoke()?.Player != null,
            ModVersion = "0.1.0"
        };
        return JsonSerializer.Serialize(ApiResponse<HealthCheck>.Ok(health), JsonOptions);
    }

    private string HandleGetState()
    {
        if (GetGameState == null)
            return JsonSerializer.Serialize(ApiResponse<GameState>.Fail("Game state reader not initialized"), JsonOptions);

        try
        {
            var state = GetGameState();
            if (state == null)
                return JsonSerializer.Serialize(ApiResponse<GameState>.Fail("No game state available (not in game?)"), JsonOptions);

            return JsonSerializer.Serialize(ApiResponse<GameState>.Ok(state), JsonOptions);
        }
        catch (Exception ex)
        {
            return JsonSerializer.Serialize(ApiResponse<GameState>.Fail($"Error reading state: {ex.Message}"), JsonOptions);
        }
    }

    private string HandleAction(HttpListenerRequest request)
    {
        if (QueueAction == null)
            return JsonSerializer.Serialize(ApiResponse<ActionResult>.Fail("Action executor not initialized"), JsonOptions);

        using var reader = new StreamReader(request.InputStream, Encoding.UTF8);
        string body = reader.ReadToEnd();

        try
        {
            var command = JsonSerializer.Deserialize<ActionCommand>(body, JsonOptions);
            if (command == null || string.IsNullOrEmpty(command.Action))
                return JsonSerializer.Serialize(ApiResponse<ActionResult>.Fail("Invalid action command"), JsonOptions);

            var result = QueueAction(command);
            return JsonSerializer.Serialize(ApiResponse<ActionResult>.Ok(result), JsonOptions);
        }
        catch (JsonException ex)
        {
            return JsonSerializer.Serialize(ApiResponse<ActionResult>.Fail($"Invalid JSON: {ex.Message}"), JsonOptions);
        }
    }

    private string HandleGetSurroundings()
    {
        if (GetSurroundings == null)
            return JsonSerializer.Serialize(ApiResponse<SurroundingsState>.Fail("Surroundings reader not initialized"), JsonOptions);

        try
        {
            var surroundings = GetSurroundings();
            if (surroundings == null)
                return JsonSerializer.Serialize(ApiResponse<SurroundingsState>.Fail("No surroundings available (not in game?)"), JsonOptions);

            return JsonSerializer.Serialize(ApiResponse<SurroundingsState>.Ok(surroundings), JsonOptions);
        }
        catch (Exception ex)
        {
            return JsonSerializer.Serialize(ApiResponse<SurroundingsState>.Fail($"Error reading surroundings: {ex.Message}"), JsonOptions);
        }
    }

    private string HandleGetFarm()
    {
        if (GetFarmState == null)
            return JsonSerializer.Serialize(ApiResponse<FarmState>.Fail("Farm state reader not initialized"), JsonOptions);

        try
        {
            var farmState = GetFarmState();
            if (farmState == null)
                return JsonSerializer.Serialize(ApiResponse<FarmState>.Fail("No farm state available (not in game?)"), JsonOptions);

            return JsonSerializer.Serialize(ApiResponse<FarmState>.Ok(farmState), JsonOptions);
        }
        catch (Exception ex)
        {
            return JsonSerializer.Serialize(ApiResponse<FarmState>.Fail($"Error reading farm state: {ex.Message}"), JsonOptions);
        }
    }

    private string HandleCheckPath(HttpListenerRequest request)
    {
        if (CheckPath == null)
            return JsonSerializer.Serialize(ApiResponse<PathCheckResult>.Fail("Pathfinder not initialized"), JsonOptions);

        try
        {
            int startX = int.Parse(request.QueryString["startX"] ?? "0");
            int startY = int.Parse(request.QueryString["startY"] ?? "0");
            int endX = int.Parse(request.QueryString["endX"] ?? "0");
            int endY = int.Parse(request.QueryString["endY"] ?? "0");

            var result = CheckPath(startX, startY, endX, endY);
            return JsonSerializer.Serialize(ApiResponse<PathCheckResult>.Ok(result), JsonOptions);
        }
        catch (Exception ex)
        {
            return JsonSerializer.Serialize(ApiResponse<PathCheckResult>.Fail($"Error checking path: {ex.Message}"), JsonOptions);
        }
    }

    private string HandlePassable(HttpListenerRequest request)
    {
        if (CheckPassable == null)
            return JsonSerializer.Serialize(ApiResponse<PassableResult>.Fail("Passability checker not initialized"), JsonOptions);

        try
        {
            int x = int.Parse(request.QueryString["x"] ?? "0");
            int y = int.Parse(request.QueryString["y"] ?? "0");

            var result = CheckPassable(x, y);
            return JsonSerializer.Serialize(ApiResponse<PassableResult>.Ok(result), JsonOptions);
        }
        catch (Exception ex)
        {
            return JsonSerializer.Serialize(ApiResponse<PassableResult>.Fail($"Error checking passability: {ex.Message}"), JsonOptions);
        }
    }

    private string HandlePassableArea(HttpListenerRequest request)
    {
        if (CheckPassableArea == null)
            return JsonSerializer.Serialize(ApiResponse<PassableAreaResult>.Fail("Area checker not initialized"), JsonOptions);

        try
        {
            int centerX = int.Parse(request.QueryString["centerX"] ?? "0");
            int centerY = int.Parse(request.QueryString["centerY"] ?? "0");
            int radius = int.Parse(request.QueryString["radius"] ?? "10");
            radius = Math.Min(radius, 25); // Limit to prevent performance issues

            var result = CheckPassableArea(centerX, centerY, radius);
            return JsonSerializer.Serialize(ApiResponse<PassableAreaResult>.Ok(result), JsonOptions);
        }
        catch (Exception ex)
        {
            return JsonSerializer.Serialize(ApiResponse<PassableAreaResult>.Fail($"Error checking area: {ex.Message}"), JsonOptions);
        }
    }

    private string HandleGetSkills()
    {
        if (GetSkills == null)
            return JsonSerializer.Serialize(ApiResponse<SkillsState>.Fail("Skills reader not initialized"), JsonOptions);

        try
        {
            var skills = GetSkills();
            if (skills == null)
                return JsonSerializer.Serialize(ApiResponse<SkillsState>.Fail("No skills available (not in game?)"), JsonOptions);

            return JsonSerializer.Serialize(ApiResponse<SkillsState>.Ok(skills), JsonOptions);
        }
        catch (Exception ex)
        {
            return JsonSerializer.Serialize(ApiResponse<SkillsState>.Fail($"Error reading skills: {ex.Message}"), JsonOptions);
        }
    }

    private string HandleGetNpcs()
    {
        if (GetNpcs == null)
            return JsonSerializer.Serialize(ApiResponse<NpcsState>.Fail("NPC reader not initialized"), JsonOptions);

        try
        {
            var npcs = GetNpcs();
            return JsonSerializer.Serialize(ApiResponse<NpcsState>.Ok(npcs), JsonOptions);
        }
        catch (Exception ex)
        {
            return JsonSerializer.Serialize(ApiResponse<NpcsState>.Fail($"Error reading NPCs: {ex.Message}"), JsonOptions);
        }
    }

    private string HandleGetAnimals()
    {
        if (GetAnimals == null)
            return JsonSerializer.Serialize(ApiResponse<AnimalsState>.Fail("Animal reader not initialized"), JsonOptions);

        try
        {
            var animals = GetAnimals();
            return JsonSerializer.Serialize(ApiResponse<AnimalsState>.Ok(animals), JsonOptions);
        }
        catch (Exception ex)
        {
            return JsonSerializer.Serialize(ApiResponse<AnimalsState>.Fail($"Error reading animals: {ex.Message}"), JsonOptions);
        }
    }

    private string HandleGetMachines()
    {
        if (GetMachines == null)
            return JsonSerializer.Serialize(ApiResponse<MachinesState>.Fail("Machine reader not initialized"), JsonOptions);

        try
        {
            var machines = GetMachines();
            return JsonSerializer.Serialize(ApiResponse<MachinesState>.Ok(machines), JsonOptions);
        }
        catch (Exception ex)
        {
            return JsonSerializer.Serialize(ApiResponse<MachinesState>.Fail($"Error reading machines: {ex.Message}"), JsonOptions);
        }
    }

    private string HandleGetCalendar()
    {
        if (GetCalendar == null)
            return JsonSerializer.Serialize(ApiResponse<CalendarState>.Fail("Calendar reader not initialized"), JsonOptions);

        try
        {
            var calendar = GetCalendar();
            return JsonSerializer.Serialize(ApiResponse<CalendarState>.Ok(calendar), JsonOptions);
        }
        catch (Exception ex)
        {
            return JsonSerializer.Serialize(ApiResponse<CalendarState>.Fail($"Error reading calendar: {ex.Message}"), JsonOptions);
        }
    }

    private string HandleGetFishing()
    {
        if (GetFishing == null)
            return JsonSerializer.Serialize(ApiResponse<FishingState>.Fail("Fishing reader not initialized"), JsonOptions);

        try
        {
            var fishing = GetFishing();
            return JsonSerializer.Serialize(ApiResponse<FishingState>.Ok(fishing), JsonOptions);
        }
        catch (Exception ex)
        {
            return JsonSerializer.Serialize(ApiResponse<FishingState>.Fail($"Error reading fishing data: {ex.Message}"), JsonOptions);
        }
    }

    private string HandleGetMining()
    {
        if (GetMining == null)
            return JsonSerializer.Serialize(ApiResponse<MiningState>.Fail("Mining reader not initialized"), JsonOptions);

        try
        {
            var mining = GetMining();
            return JsonSerializer.Serialize(ApiResponse<MiningState>.Ok(mining), JsonOptions);
        }
        catch (Exception ex)
        {
            return JsonSerializer.Serialize(ApiResponse<MiningState>.Fail($"Error reading mining data: {ex.Message}"), JsonOptions);
        }
    }

    private string HandleGetStorage()
    {
        if (GetStorage == null)
            return JsonSerializer.Serialize(ApiResponse<StorageState>.Fail("Storage reader not initialized"), JsonOptions);

        try
        {
            var storage = GetStorage();
            return JsonSerializer.Serialize(ApiResponse<StorageState>.Ok(storage), JsonOptions);
        }
        catch (Exception ex)
        {
            return JsonSerializer.Serialize(ApiResponse<StorageState>.Fail($"Error reading storage: {ex.Message}"), JsonOptions);
        }
    }

    private void SendResponse(HttpListenerResponse response, string json, int statusCode = 200)
    {
        response.StatusCode = statusCode;
        response.ContentType = "application/json";
        response.AddHeader("Access-Control-Allow-Origin", "*");

        byte[] buffer = Encoding.UTF8.GetBytes(json);
        response.ContentLength64 = buffer.Length;
        response.OutputStream.Write(buffer, 0, buffer.Length);
        response.OutputStream.Close();
    }

    public void Dispose()
    {
        Stop();
        _listener?.Close();
    }
}
