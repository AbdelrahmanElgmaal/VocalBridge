using VocalBridge.Domain.Common;
using VocalBridge.Domain.Enums;

namespace VocalBridge.Domain.Entities;

/// <summary>
/// Represents a video source — either an uploaded file or an external URL.
/// Uploaded files are stored in Supabase Storage (private bucket).
/// External URLs are passed directly to the AI Service.
/// </summary>
public class Video : BaseEntity
{
    public Guid UserId { get; set; }
    public string FileName { get; set; } = string.Empty;
    public VideoSourceType SourceType { get; set; }

    /// <summary>
    /// Path in Supabase Storage. Set only when SourceType == Uploaded.
    /// </summary>
    public string? StoragePath { get; set; }

    /// <summary>
    /// Original public URL (YouTube, Vimeo, direct link, etc.).
    /// Set only when SourceType == ExternalUrl.
    /// </summary>
    public string? OriginalVideoUrl { get; set; }

    /// <summary>File size in bytes. Only available for uploaded files.</summary>
    public long? FileSize { get; set; }

    // ── Navigation Properties ──
    public User User { get; set; } = null!;
    public ICollection<TranslationJob> TranslationJobs { get; set; } = new List<TranslationJob>();
}
