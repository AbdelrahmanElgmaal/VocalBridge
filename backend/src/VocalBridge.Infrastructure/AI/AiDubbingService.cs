using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Serialization;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using VocalBridge.Application.Common;
using VocalBridge.Application.DTOs.Translations;
using VocalBridge.Application.Interfaces;
using VocalBridge.Infrastructure.AI.Settings;

namespace VocalBridge.Infrastructure.AI;

/// <summary>
/// Implements IAiService — communicates with the Python FastAPI AI Service.
/// Language is hardcoded: English → Arabic.
/// Returns Result&lt;T&gt; for all operations — never crashes the application.
/// </summary>
public class AiDubbingService : IAiService
{
    private readonly HttpClient _http;
    private readonly AiServiceSettings _settings;
    private readonly ILogger<AiDubbingService> _logger;

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
    };

    public AiDubbingService(HttpClient http, IOptions<AiServiceSettings> settings,
                             ILogger<AiDubbingService> logger)
    {
        _http = http;
        _settings = settings.Value;
        _logger = logger;
        _http.BaseAddress = new Uri(_settings.BaseUrl);
        _http.Timeout = TimeSpan.FromSeconds(_settings.TimeoutSeconds);
    }

    public async Task<Result<string>> StartJobAsync(string videoUrl, string? webhookUrl,
                                                     CreateTranslationRequest? options = null,
                                                     CancellationToken ct = default)
    {
        try
        {
            var payload = new Dictionary<string, object?>
            {
                ["video_url"] = videoUrl,
                ["input_type"] = options?.InputType.ToString().ToLower() ?? "video",
                ["target_language"] = "ar",
                ["source_language"] = "en",
                ["webhook_url"] = webhookUrl ?? _settings.WebhookCallbackUrl,
                ["clone_speaker"] = options?.VoiceCloning ?? true,
                ["burn_subtitles"] = options?.BurnSubtitles ?? true,
                ["enable_lipsync"] = options?.EnableLipsync ?? false,
            };

            // Only send manual voice config when voice cloning is OFF
            if (options is not null && !options.VoiceCloning)
            {
                payload["voice_gender"] = options.VoiceGender ?? "male";
                payload["voice_age"] = options.VoiceAge;
                payload["voice_pitch"] = options.VoicePitch;
                payload["voice_style"] = options.VoiceStyle;
            }

            _logger.LogInformation("Starting AI job for video URL: {Url}", videoUrl);

            var response = await _http.PostAsJsonAsync("/api/dubbing/start", payload, JsonOptions, ct);

            if (!response.IsSuccessStatusCode)
            {
                var body = await response.Content.ReadAsStringAsync(ct);
                _logger.LogError("AI Service returned {StatusCode}: {Body}",
                    (int)response.StatusCode, body);
                return Result<string>.Failure($"AI Service error ({(int)response.StatusCode}): {body}");
            }

            var result = await response.Content.ReadFromJsonAsync<AiStartResponse>(JsonOptions, ct);
            if (result?.JobId is null)
                return Result<string>.Failure("AI Service returned no job_id.");

            _logger.LogInformation("AI job created: {JobId}", result.JobId);
            return Result<string>.Success(result.JobId);
        }
        catch (TaskCanceledException) when (!ct.IsCancellationRequested)
        {
            _logger.LogError("AI Service request timed out");
            return Result<string>.Failure("AI Service request timed out.");
        }
        catch (HttpRequestException ex)
        {
            _logger.LogError(ex, "AI Service network error");
            return Result<string>.Failure($"AI Service unreachable: {ex.Message}");
        }
    }

    public async Task<Result<AiJobStatusDto>> GetStatusAsync(string aiJobId, CancellationToken ct = default)
    {
        try
        {
            var response = await _http.GetAsync($"/api/dubbing/status/{aiJobId}", ct);

            if (!response.IsSuccessStatusCode)
            {
                var body = await response.Content.ReadAsStringAsync(ct);
                return Result<AiJobStatusDto>.Failure($"Status check failed ({(int)response.StatusCode}): {body}");
            }

            var result = await response.Content.ReadFromJsonAsync<AiJobStatusDto>(JsonOptions, ct);
            return result is not null
                ? Result<AiJobStatusDto>.Success(result)
                : Result<AiJobStatusDto>.Failure("AI Service returned empty status.");
        }
        catch (TaskCanceledException) when (!ct.IsCancellationRequested)
        {
            return Result<AiJobStatusDto>.Failure("AI Service request timed out.");
        }
        catch (HttpRequestException ex)
        {
            return Result<AiJobStatusDto>.Failure($"AI Service unreachable: {ex.Message}");
        }
    }

    public async Task<Result> CancelJobAsync(string aiJobId, CancellationToken ct = default)
    {
        try
        {
            var response = await _http.PostAsync($"/api/dubbing/cancel/{aiJobId}", null, ct);
            return response.IsSuccessStatusCode
                ? Result.Success()
                : Result.Failure($"Cancel failed ({(int)response.StatusCode}).");
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to cancel AI job {AiJobId}", aiJobId);
            return Result.Failure($"Cancel request failed: {ex.Message}");
        }
    }

    public async Task<Result<Stream>> DownloadResultAsync(string aiJobId, bool isAudio = false, CancellationToken ct = default)
    {
        try
        {
            _logger.LogInformation("Downloading translated video for AI job {AiJobId}", aiJobId);

            var ext = isAudio ? "wav" : "mp4";
            var response = await _http.GetAsync(
                $"/api/dubbing/download/{aiJobId}.{ext}",
                HttpCompletionOption.ResponseHeadersRead, ct);

            if (!response.IsSuccessStatusCode)
            {
                var body = await response.Content.ReadAsStringAsync(ct);
                return Result<Stream>.Failure($"Download failed ({(int)response.StatusCode}): {body}");
            }

            var stream = await response.Content.ReadAsStreamAsync(ct);
            return Result<Stream>.Success(stream);
        }
        catch (TaskCanceledException) when (!ct.IsCancellationRequested)
        {
            return Result<Stream>.Failure("Download timed out.");
        }
        catch (HttpRequestException ex)
        {
            _logger.LogError(ex, "Download failed for AI job {AiJobId}", aiJobId);
            return Result<Stream>.Failure($"Download failed: {ex.Message}");
        }
    }

    public async Task<bool> IsHealthyAsync(CancellationToken ct = default)
    {
        try
        {
            var response = await _http.GetAsync("/health", ct);
            return response.IsSuccessStatusCode;
        }
        catch
        {
            return false;
        }
    }

    private class AiStartResponse
    {
        [JsonPropertyName("job_id")]
        public string? JobId { get; set; }

        [JsonPropertyName("status")]
        public string? Status { get; set; }
    }
}
