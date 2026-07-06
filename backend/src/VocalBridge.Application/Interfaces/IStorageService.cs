namespace VocalBridge.Application.Interfaces;

/// <summary>
/// Abstracts cloud file storage (Supabase, Azure Blob, S3, etc.).
/// Application layer doesn't know which provider is used.
/// </summary>
public interface IStorageService
{
    /// <summary>Upload a file and return its storage path.</summary>
    Task<string> UploadFileAsync(Stream fileStream, string fileName, string folder,
                                  CancellationToken ct = default);

    /// <summary>Generate a time-limited signed URL for secure access.</summary>
    Task<string> GetSignedUrlAsync(string storagePath, int expiresInSeconds = 3600,
                                    CancellationToken ct = default);

    /// <summary>Delete a file from storage. No-op if file doesn't exist.</summary>
    Task DeleteFileAsync(string storagePath, CancellationToken ct = default);

    /// <summary>Check if the storage service is reachable.</summary>
    Task<bool> IsHealthyAsync(CancellationToken ct = default);
}
