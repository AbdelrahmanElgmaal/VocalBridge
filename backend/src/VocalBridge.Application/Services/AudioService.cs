using AutoMapper;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;
using VocalBridge.Application.Common;
using VocalBridge.Application.DTOs.Audios;
using VocalBridge.Application.Interfaces;
using VocalBridge.Domain.Entities;
using VocalBridge.Domain.Enums;
using TagLib;

namespace VocalBridge.Application.Services;

/// <summary>
/// Handles audio upload, metadata extraction, validation, and listing.
/// </summary>
public class AudioService
{
    private readonly IAppDbContext _db;
    private readonly IStorageService _storage;
    private readonly ILogger<AudioService> _logger;

    private static readonly HashSet<string> AllowedExtensions = new(StringComparer.OrdinalIgnoreCase)
    {
        ".mp3", ".wav", ".m4a", ".webm", ".ogg"
    };

    private static readonly HashSet<string> AllowedMimeTypes = new(StringComparer.OrdinalIgnoreCase)
    {
        "audio/mpeg", "audio/wav", "audio/x-wav", "audio/x-m4a", "audio/mp4", "application/octet-stream", "audio/webm", "video/webm", "audio/ogg", "application/ogg"
    };

    private const long MaxFileSizeBytes = 10 * 1024 * 1024; // 10 MB
    private const double MaxDurationSeconds = 25.0;

    public AudioService(IAppDbContext db, IStorageService storage, ILogger<AudioService> logger)
    {
        _db = db;
        _storage = storage;
        _logger = logger;
    }

    /// <summary>Upload a local audio file to Supabase Storage.</summary>
    public async Task<Result<AudioDto>> UploadAsync(Stream fileStream, string fileName,
                                                     string contentType, long fileSize,
                                                     AudioSourceType sourceType,
                                                     Guid userId, CancellationToken ct = default)
    {
        _logger.LogInformation("[TRACE] Starting upload. FileName={FileName}, ContentType={ContentType}, FileSize={FileSize}, SourceType={SourceType}", fileName, contentType, fileSize, sourceType);

        // Validate file
        var extension = Path.GetExtension(fileName);
        _logger.LogInformation("[TRACE] Extracted extension: {Extension}", extension);
        
        if (!AllowedExtensions.Contains(extension))
        {
            _logger.LogWarning("[TRACE] Validation failed: Unsupported file type '{Extension}'", extension);
            return Result<AudioDto>.Failure($"Unsupported file type '{extension}'. Allowed: {string.Join(", ", AllowedExtensions)}");
        }

        var baseMimeType = contentType?.Split(';')[0].Trim() ?? "";
        _logger.LogInformation("[TRACE] Extracted base MIME type: {BaseMimeType} from {ContentType}", baseMimeType, contentType);

        if (!AllowedMimeTypes.Contains(baseMimeType))
        {
            _logger.LogWarning("[TRACE] Validation failed: Unsupported MIME type '{ContentType}'", contentType);
            return Result<AudioDto>.Failure($"Unsupported MIME type '{contentType}'.");
        }

        if (fileSize > MaxFileSizeBytes)
        {
            _logger.LogWarning("[TRACE] Validation failed: File too large ({FileSize} bytes)", fileSize);
            return Result<AudioDto>.Failure($"File too large. Maximum size is {MaxFileSizeBytes / (1024 * 1024)} MB.");
        }

        if (fileSize == 0)
        {
            _logger.LogWarning("[TRACE] Validation failed: File is empty");
            return Result<AudioDto>.Failure("File is empty.");
        }

        // Read duration using TagLib#
        double durationSeconds = 0;
        var tempPath = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString() + extension);
        try
        {
            using (var fileStreamOutput = System.IO.File.Create(tempPath))
            {
                fileStream.Position = 0;
                await fileStream.CopyToAsync(fileStreamOutput, ct);
            }

            using var tagFile = TagLib.File.Create(tempPath);
            durationSeconds = tagFile.Properties.Duration.TotalSeconds;

            if (durationSeconds > MaxDurationSeconds)
                return Result<AudioDto>.Failure($"Audio duration ({durationSeconds:F1}s) exceeds the maximum allowed ({MaxDurationSeconds}s).");
            
            if (durationSeconds <= 0)
                return Result<AudioDto>.Failure("Could not determine audio duration or file is empty.");
                
            // Reset stream position for Supabase upload
            fileStream.Position = 0;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to read audio metadata. Assuming browser fallback.");
            return Result<AudioDto>.Failure("Failed to read audio duration. The recording may be corrupted or in an unsupported codec format.");
        }
        finally
        {
            if (System.IO.File.Exists(tempPath))
                System.IO.File.Delete(tempPath);
        }

        _logger.LogInformation("[TRACE] Validation passed. Read duration: {Duration}s", durationSeconds);

        _logger.LogInformation("[TRACE] Uploading to Supabase");
        var storagePath = await _storage.UploadFileAsync(fileStream, fileName,
            $"users/{userId}/audio", ct);
        _logger.LogInformation("[TRACE] Upload completed. Storage Path: {Path}", storagePath);

        _logger.LogInformation("[TRACE] Creating Audio entity");
        var audio = new Audio
        {
            UserId = userId,
            FileName = Path.GetFileNameWithoutExtension(fileName) + extension,
            DurationSeconds = durationSeconds,
            SourceType = sourceType,
            StoragePath = storagePath,
            FileSize = fileSize
        };

        _db.Audios.Add(audio);
        _logger.LogInformation("[TRACE] SaveChangesAsync started");
        await _db.SaveChangesAsync(ct);
        _logger.LogInformation("[TRACE] SaveChangesAsync completed");

        _logger.LogInformation("Audio uploaded: {AudioId} → {StoragePath}", audio.Id, storagePath);

        var dto = new AudioDto
        {
            Id = audio.Id,
            FileName = audio.FileName,
            DurationSeconds = audio.DurationSeconds,
            FileSize = audio.FileSize,
            SourceType = audio.SourceType.ToString(),
            CreatedAt = audio.CreatedAt,
            Url = await _storage.GetSignedUrlAsync(storagePath, ct: ct)
        };
        
        _logger.LogInformation("[TRACE] Returning AudioDto to controller");
        return Result<AudioDto>.Success(dto);
    }
    
    public async Task<Result<AudioDto>> GetByIdAsync(Guid audioId, Guid userId, CancellationToken ct = default)
    {
        var audio = await _db.Audios
            .FirstOrDefaultAsync(a => a.Id == audioId && a.UserId == userId, ct);

        if (audio is null)
            return Result<AudioDto>.Failure("Audio not found.");

        var dto = new AudioDto
        {
            Id = audio.Id,
            FileName = audio.FileName,
            DurationSeconds = audio.DurationSeconds,
            FileSize = audio.FileSize,
            SourceType = audio.SourceType.ToString(),
            CreatedAt = audio.CreatedAt,
            Url = audio.StoragePath is not null 
                ? await _storage.GetSignedUrlAsync(audio.StoragePath, ct: ct)
                : audio.OriginalAudioUrl
        };

        return Result<AudioDto>.Success(dto);
    }

    public async Task<Result<List<AudioDto>>> GetAllByUserAsync(Guid userId, CancellationToken ct = default)
    {
        var audios = await _db.Audios
            .Where(a => a.UserId == userId)
            .OrderByDescending(a => a.CreatedAt)
            .ToListAsync(ct);

        var dtos = new List<AudioDto>();
        foreach (var audio in audios)
        {
            dtos.Add(new AudioDto
            {
                Id = audio.Id,
                FileName = audio.FileName,
                DurationSeconds = audio.DurationSeconds,
                FileSize = audio.FileSize,
                SourceType = audio.SourceType.ToString(),
                CreatedAt = audio.CreatedAt,
                Url = audio.StoragePath is not null
                    ? await _storage.GetSignedUrlAsync(audio.StoragePath, ct: ct)
                    : audio.OriginalAudioUrl
            });
        }

        return Result<List<AudioDto>>.Success(dtos);
    }

    public async Task<Result> DeleteAsync(Guid audioId, Guid userId, CancellationToken ct = default)
    {
        var audio = await _db.Audios
            .FirstOrDefaultAsync(a => a.Id == audioId && a.UserId == userId, ct);

        if (audio is null)
            return Result.Failure("Audio not found.");

        var jobs = await _db.TranslationJobs
            .Where(j => j.AudioId == audioId && j.UserId == userId)
            .ToListAsync(ct);

        if (audio.StoragePath is not null)
        {
            _logger.LogInformation("Deleting original audio file: {Path}", audio.StoragePath);
            await _storage.DeleteFileAsync(audio.StoragePath, ct);
        }

        foreach (var job in jobs)
        {
            if (job.TranslatedAudioPath is not null)
            {
                _logger.LogInformation("Deleting translated audio file: {Path}", job.TranslatedAudioPath);
                await _storage.DeleteFileAsync(job.TranslatedAudioPath, ct);
            }
        }

        _db.TranslationJobs.RemoveRange(jobs);
        _db.Audios.Remove(audio);
        await _db.SaveChangesAsync(ct);

        _logger.LogInformation("Audio deleted: {AudioId}", audioId);
        return Result.Success();
    }
}
