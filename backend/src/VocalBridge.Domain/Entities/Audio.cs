using VocalBridge.Domain.Common;
using VocalBridge.Domain.Enums;

namespace VocalBridge.Domain.Entities;

/// <summary>
/// Represents an uploaded or linked audio file to be dubbed.
/// </summary>
public class Audio : BaseEntity
{
    public Guid UserId { get; set; }
    
    public AudioSourceType SourceType { get; set; }

    /// <summary>Original display name of the file (e.g. "speech.mp3").</summary>
    public string FileName { get; set; } = string.Empty;

    /// <summary>Size of the file in bytes.</summary>
    public long FileSize { get; set; }

    /// <summary>Exact duration of the audio in seconds.</summary>
    public double DurationSeconds { get; set; }

    /// <summary>Path in cloud storage (e.g., users/{userId}/audio/{id}.mp3).</summary>
    public string? StoragePath { get; set; }

    /// <summary>External URL if the audio was not uploaded directly.</summary>
    public string? OriginalAudioUrl { get; set; }

    // ── Navigation Properties ──
    public User User { get; set; } = null!;
}
