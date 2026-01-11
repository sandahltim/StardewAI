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
