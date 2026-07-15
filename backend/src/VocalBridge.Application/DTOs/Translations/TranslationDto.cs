using VocalBridge.Application.DTOs.Videos;
using VocalBridge.Application.DTOs.Audios;
using VocalBridge.Domain.Enums;

namespace VocalBridge.Application.DTOs.Translations;

public class TranslationDto
{
    public Guid Id { get; set; }
    public Guid UserId { get; set; }
    
    public InputType InputType { get; set; }
    public OutputType OutputType { get; set; }

    public string Status { get; set; } = string.Empty;
    public double Progress { get; set; }
    public string? CurrentStage { get; set; }

    public string? TranslatedVideoUrl { get; set; }
    public string? TranslatedAudioUrl { get; set; }
    public string? ErrorMessage { get; set; }
    public string? Transcript { get; set; }
    public string? TranslatedText { get; set; }
    public string? VideoFileName { get; set; }
    public DateTime CreatedAt { get; set; }
    public DateTime? CompletedAt { get; set; }
    public bool? VoiceCloning { get; set; }
    public bool? BurnSubtitles { get; set; }
    public bool? EnableLipsync { get; set; }
    public string? VoiceGender { get; set; }
    public string? VoiceAge { get; set; }
    public string? VoicePitch { get; set; }
    public string? VoiceStyle { get; set; }

    public VideoDto? Video { get; set; }
    public AudioDto? Audio { get; set; }
}
