namespace VocalBridge.Application.DTOs.Audios;

public class AudioDto
{
    public Guid Id { get; set; }
    public string FileName { get; set; } = string.Empty;
    public long FileSize { get; set; }
    public double DurationSeconds { get; set; }
    public string SourceType { get; set; } = string.Empty;
    public DateTime CreatedAt { get; set; }

    /// <summary>
    /// Signed URL for uploaded audios, original URL for external audios.
    /// </summary>
    public string? Url { get; set; }
}
