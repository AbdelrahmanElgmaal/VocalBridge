namespace VocalBridge.Domain.Enums;

/// <summary>
/// Indicates how the original video was provided.
/// </summary>
public enum VideoSourceType
{
    /// <summary>User uploaded a file — stored in Supabase Storage.</summary>
    Uploaded = 0,

    /// <summary>User submitted a public URL (YouTube, Vimeo, direct link, etc.).</summary>
    ExternalUrl = 1
}
