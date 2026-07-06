using VocalBridge.Domain.Common;
using VocalBridge.Domain.Enums;

namespace VocalBridge.Domain.Entities;

/// <summary>
/// Represents a single English → Arabic video dubbing request.
/// Tracks the full lifecycle from creation through AI processing to completion.
/// Language is fixed: always English → Arabic. No language selection.
/// </summary>
public class TranslationJob : BaseEntity
{
    public Guid? VideoId { get; set; }
    public Guid? AudioId { get; set; }
    public Guid UserId { get; set; }

    /// <summary>The job_id returned by the external AI Service.</summary>
    public string? AiJobId { get; set; }

    public TranslationStatus Status { get; set; } = TranslationStatus.Queued;
    public double Progress { get; set; }

    /// <summary>
    /// Path of the translated Arabic video in Supabase Storage.
    /// Null until the job completes and the result is uploaded.
    /// </summary>
    public string? TranslatedVideoPath { get; set; }

    /// <summary>
    /// Path of the translated Arabic audio in Supabase Storage.
    /// Null until the job completes and the result is uploaded.
    /// </summary>
    public string? TranslatedAudioPath { get; set; }

    public InputType InputType { get; set; } = InputType.Video;
    public OutputType OutputType { get; set; } = OutputType.Video;

    /// <summary>Error details if the job failed. Null otherwise.</summary>
    public string? ErrorMessage { get; set; }

    /// <summary>Current AI pipeline stage reported by the Python service.</summary>
    public string? CurrentStage { get; set; }

    /// <summary>Live English transcript produced by speech recognition.</summary>
    public string? Transcript { get; set; }

    /// <summary>Live Arabic translation produced by the translation stage.</summary>
    public string? TranslatedText { get; set; }

    public DateTime? CompletedAt { get; set; }

    // ── Voice Settings (persisted for retry) ──

    /// <summary>Whether voice cloning was used. Null for legacy jobs.</summary>
    public bool? VoiceCloning { get; set; }

    /// <summary>Whether subtitles were burned into the output.</summary>
    public bool? BurnSubtitles { get; set; }

    /// <summary>Manual voice gender (when cloning is disabled).</summary>
    public string? VoiceGender { get; set; }

    /// <summary>Manual voice age (when cloning is disabled).</summary>
    public string? VoiceAge { get; set; }

    /// <summary>Manual voice pitch (when cloning is disabled).</summary>
    public string? VoicePitch { get; set; }

    /// <summary>Manual voice style (when cloning is disabled).</summary>
    public string? VoiceStyle { get; set; }

    // ── Navigation Properties ──
    public Video? Video { get; set; }
    public Audio? Audio { get; set; }
    public User User { get; set; } = null!;
}
