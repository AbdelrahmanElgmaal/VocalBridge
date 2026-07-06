using System.Text.Json.Serialization;

namespace VocalBridge.Application.DTOs.Translations;

/// <summary>
/// Represents the status response from the external AI Service.
/// Maps directly to the AI's status/webhook JSON contract.
/// </summary>
public class AiJobStatusDto
{
    [JsonPropertyName("job_id")]
    public string JobId { get; set; } = string.Empty;

    [JsonPropertyName("status")]
    public string Status { get; set; } = string.Empty;

    [JsonPropertyName("progress")]
    public double Progress { get; set; }

    [JsonPropertyName("translated_video_url")]
    public string? TranslatedVideoUrl { get; set; }

    [JsonPropertyName("error_message")]
    public string? ErrorMessage { get; set; }

    [JsonPropertyName("currentStage")]
    public string? CurrentStage { get; set; }

    [JsonPropertyName("transcript")]
    public string? Transcript { get; set; }

    [JsonPropertyName("translatedText")]
    public string? TranslatedText { get; set; }
}
