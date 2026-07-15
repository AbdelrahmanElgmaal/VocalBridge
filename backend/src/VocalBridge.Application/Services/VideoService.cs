using AutoMapper;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;
using VocalBridge.Application.Common;
using VocalBridge.Application.DTOs.Videos;
using VocalBridge.Application.Interfaces;
using VocalBridge.Domain.Entities;
using VocalBridge.Domain.Enums;

namespace VocalBridge.Application.Services;

/// <summary>
/// Handles video upload (file + URL), listing, and deletion.
/// </summary>
public class VideoService
{
    private readonly IAppDbContext _db;
    private readonly IStorageService _storage;
    private readonly IMapper _mapper;
    private readonly ILogger<VideoService> _logger;

    private static readonly HashSet<string> AllowedExtensions = new(StringComparer.OrdinalIgnoreCase)
    {
        ".mp4", ".mov", ".avi", ".mkv", ".webm", ".wmv", ".flv"
    };

    private static readonly HashSet<string> AllowedMimeTypes = new(StringComparer.OrdinalIgnoreCase)
    {
        "video/mp4", "video/quicktime", "video/x-msvideo", "video/x-matroska",
        "video/webm", "video/x-ms-wmv", "video/x-flv", "application/octet-stream"
    };

    private const long MaxFileSizeBytes = 500 * 1024 * 1024; // 500 MB

    public VideoService(IAppDbContext db, IStorageService storage, IMapper mapper,
                        ILogger<VideoService> logger)
    {
        _db = db;
        _storage = storage;
        _mapper = mapper;
        _logger = logger;
    }

    /// <summary>Upload a local video file to Supabase Storage.</summary>
    public async Task<Result<VideoDto>> UploadAsync(Stream fileStream, string fileName,
                                                     string contentType, long fileSize,
                                                     Guid userId, CancellationToken ct = default)
    {
        // Validate file
        var extension = Path.GetExtension(fileName);
        if (!AllowedExtensions.Contains(extension))
            return Result<VideoDto>.Failure($"Unsupported file type '{extension}'. Allowed: {string.Join(", ", AllowedExtensions)}");

        if (!AllowedMimeTypes.Contains(contentType))
            return Result<VideoDto>.Failure($"Unsupported MIME type '{contentType}'.");

        if (fileSize > MaxFileSizeBytes)
            return Result<VideoDto>.Failure($"File too large. Maximum size is {MaxFileSizeBytes / (1024 * 1024)} MB.");

        if (fileSize == 0)
            return Result<VideoDto>.Failure("File is empty.");

        _logger.LogInformation("Uploading video {FileName} ({Size} bytes) for user {UserId}",
            fileName, fileSize, userId);

        // Upload to Supabase
        var storagePath = await _storage.UploadFileAsync(fileStream, fileName,
            $"users/{userId}/videos", ct);

        // Save metadata
        var video = new Video
        {
            UserId = userId,
            FileName = Path.GetFileNameWithoutExtension(fileName) + extension,
            SourceType = VideoSourceType.Uploaded,
            StoragePath = storagePath,
            FileSize = fileSize
        };

        _db.Videos.Add(video);
        await _db.SaveChangesAsync(ct);

        _logger.LogInformation("Video uploaded: {VideoId} → {StoragePath}", video.Id, storagePath);

        var dto = _mapper.Map<VideoDto>(video);
        dto.Url = await _storage.GetSignedUrlAsync(storagePath, ct: ct);
        return Result<VideoDto>.Success(dto);
    }

    /// <summary>Register an external video URL (YouTube, Vimeo, etc.).</summary>
    public async Task<Result<VideoDto>> CreateFromUrlAsync(string videoUrl, Guid userId,
                                                            CancellationToken ct = default)
    {
        _logger.LogInformation("Registering external video URL for user {UserId}: {Url}", userId, videoUrl);

        // Extract a display name from the URL
        var uri = new Uri(videoUrl);
        var fileName = Path.GetFileName(uri.AbsolutePath);
        if (string.IsNullOrWhiteSpace(fileName) || !fileName.Contains('.'))
            fileName = $"{uri.Host}_video";

        var video = new Video
        {
            UserId = userId,
            FileName = fileName,
            SourceType = VideoSourceType.ExternalUrl,
            OriginalVideoUrl = videoUrl
        };

        _db.Videos.Add(video);
        await _db.SaveChangesAsync(ct);

        _logger.LogInformation("External video registered: {VideoId}", video.Id);

        var dto = _mapper.Map<VideoDto>(video);
        dto.Url = videoUrl; // Return the original URL
        return Result<VideoDto>.Success(dto);
    }

    public async Task<Result<List<VideoDto>>> GetAllByUserAsync(Guid userId, CancellationToken ct = default)
    {
        var videos = await _db.Videos
            .Where(v => v.UserId == userId)
            .OrderByDescending(v => v.CreatedAt)
            .ToListAsync(ct);

        var dtos = _mapper.Map<List<VideoDto>>(videos);

        foreach (var (dto, video) in dtos.Zip(videos))
        {
            if (video.SourceType == VideoSourceType.Uploaded && video.StoragePath is not null)
            {
                try
                {
                    dto.Url = await _storage.GetSignedUrlAsync(video.StoragePath, ct: ct);
                }
                catch (Exception ex)
                {
                    _logger.LogWarning("Could not generate signed URL for video {VideoId} (path: {Path}): {Message}",
                        video.Id, video.StoragePath, ex.Message);
                    dto.Url = null; // File missing from storage — surface gracefully
                }
            }
            else
            {
                dto.Url = video.OriginalVideoUrl;
            }
        }

        return Result<List<VideoDto>>.Success(dtos);
    }

    public async Task<Result<VideoDto>> GetByIdAsync(Guid videoId, Guid userId, CancellationToken ct = default)
    {
        var video = await _db.Videos
            .FirstOrDefaultAsync(v => v.Id == videoId && v.UserId == userId, ct);

        if (video is null)
            return Result<VideoDto>.Failure("Video not found.");

        var dto = _mapper.Map<VideoDto>(video);
        if (video.SourceType == VideoSourceType.Uploaded && video.StoragePath is not null)
        {
            try
            {
                dto.Url = await _storage.GetSignedUrlAsync(video.StoragePath, ct: ct);
            }
            catch (Exception ex)
            {
                _logger.LogWarning("Could not generate signed URL for video {VideoId} (path: {Path}): {Message}",
                    video.Id, video.StoragePath, ex.Message);
                dto.Url = null;
            }
        }
        else
        {
            dto.Url = video.OriginalVideoUrl;
        }

        return Result<VideoDto>.Success(dto);
    }

    public async Task<Result> DeleteAsync(Guid videoId, Guid userId, CancellationToken ct = default)
    {
        var video = await _db.Videos
            .Include(v => v.TranslationJobs)
            .FirstOrDefaultAsync(v => v.Id == videoId && v.UserId == userId, ct);

        if (video is null)
            return Result.Failure("Video not found.");

        // Delete uploaded files from Supabase (only for uploaded videos)
        if (video.SourceType == VideoSourceType.Uploaded && video.StoragePath is not null)
        {
            _logger.LogInformation("Deleting original file: {Path}", video.StoragePath);
            await _storage.DeleteFileAsync(video.StoragePath, ct);
        }

        // Delete translated videos from Supabase
        foreach (var job in video.TranslationJobs)
        {
            if (job.TranslatedVideoPath is not null)
            {
                _logger.LogInformation("Deleting translated file: {Path}", job.TranslatedVideoPath);
                await _storage.DeleteFileAsync(job.TranslatedVideoPath, ct);
            }
        }

        _db.Videos.Remove(video);
        await _db.SaveChangesAsync(ct);

        _logger.LogInformation("Video deleted: {VideoId}", videoId);
        return Result.Success();
    }
}
