using VocalBridge.Domain.Enums;

namespace VocalBridge.Application.DTOs.Translations;

/// <summary>
/// Request to start a new English → Arabic translation job.
/// Exactly ONE source must be provided: either VideoId, VideoUrl, or AudioId.
/// </summary>
public class CreateTranslationRequest
{
    /// <summary>ID of an existing uploaded video.</summary>
    public Guid? VideoId { get; set; }

    /// <summary>Public video URL (YouTube, Vimeo, direct link).</summary>
    public string? VideoUrl { get; set; }

    /// <summary>ID of an existing uploaded audio.</summary>
    public Guid? AudioId { get; set; }

    /// <summary>Type of input media (Video or Audio).</summary>
    public InputType InputType { get; set; } = InputType.Video;

    /// <summary>Enable AI voice cloning from the original speaker. Default: true.</summary>
    public bool VoiceCloning { get; set; } = true;

    /// <summary>Burn translated subtitles into the output video. Default: true.</summary>
    public bool BurnSubtitles { get; set; } = true;

    /// <summary>TTS voice gender when voice cloning is disabled. Values: male, female.</summary>
    public string? VoiceGender { get; set; }

    /// <summary>TTS voice age when voice cloning is disabled.</summary>
    public string? VoiceAge { get; set; }

    /// <summary>TTS voice pitch when voice cloning is disabled.</summary>
    public string? VoicePitch { get; set; }

    /// <summary>TTS voice style when voice cloning is disabled. Values: natural, whisper.</summary>
    public string? VoiceStyle { get; set; }
}
