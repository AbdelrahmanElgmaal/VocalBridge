using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using Supabase;
using VocalBridge.Application.Interfaces;
using VocalBridge.Infrastructure.Storage.Settings;

namespace VocalBridge.Infrastructure.Storage;

/// <summary>
/// Implements IStorageService using Supabase Storage (private bucket).
/// </summary>
public class SupabaseStorageService : IStorageService
{
    private readonly Client _supabase;
    private readonly string _bucket;
    private readonly ILogger<SupabaseStorageService> _logger;

    public SupabaseStorageService(IOptions<SupabaseSettings> settings,
                                   ILogger<SupabaseStorageService> logger)
    {
        var config = settings.Value;
        _bucket = config.BucketName;
        _logger = logger;
        _supabase = new Client(config.Url, config.ServiceKey);
        _supabase.InitializeAsync().GetAwaiter().GetResult();
    }

    public async Task<string> UploadFileAsync(Stream fileStream, string fileName, string folder,
                                               CancellationToken ct = default)
    {
        var storagePath = $"{folder}/{Guid.NewGuid():N}_{fileName}";

        using var ms = new MemoryStream();
        await fileStream.CopyToAsync(ms, ct);
        var bytes = ms.ToArray();

        _logger.LogInformation("Uploading to Supabase: {Path} ({Size} bytes)", storagePath, bytes.Length);

        await _supabase.Storage
            .From(_bucket)
            .Upload(bytes, storagePath);

        return storagePath;
    }

    public async Task<string> GetSignedUrlAsync(string storagePath, int expiresInSeconds = 3600,
                                                  CancellationToken ct = default)
    {
        return await _supabase.Storage
            .From(_bucket)
            .CreateSignedUrl(storagePath, expiresInSeconds);
    }

    public async Task DeleteFileAsync(string storagePath, CancellationToken ct = default)
    {
        try
        {
            _logger.LogInformation("Deleting from Supabase: {Path}", storagePath);
            await _supabase.Storage
                .From(_bucket)
                .Remove(new List<string> { storagePath });
        }
        catch (Exception ex)
        {
            // Log but don't throw — file may already be deleted
            _logger.LogWarning(ex, "Failed to delete from Supabase: {Path}", storagePath);
        }
    }

    public async Task<bool> IsHealthyAsync(CancellationToken ct = default)
    {
        try
        {
            await _supabase.Storage.ListBuckets();
            return true;
        }
        catch
        {
            return false;
        }
    }
}
