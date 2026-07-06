namespace VocalBridge.Application.DTOs.Videos;

public class VideoDto
{
    public Guid Id { get; set; }
    public string FileName { get; set; } = string.Empty;
    public string SourceType { get; set; } = string.Empty;
    public long? FileSize { get; set; }
    public DateTime UploadedAt { get; set; }

    /// <summary>
    /// Signed URL for uploaded videos, original URL for external videos.
    /// </summary>
    public string? Url { get; set; }
}
