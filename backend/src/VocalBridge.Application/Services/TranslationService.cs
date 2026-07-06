using AutoMapper;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;
using VocalBridge.Application.Common;
using VocalBridge.Application.DTOs.Translations;
using VocalBridge.Application.Interfaces;
using VocalBridge.Domain.Entities;
using VocalBridge.Domain.Enums;

namespace VocalBridge.Application.Services;

/// <summary>
/// Orchestrates the full English → Arabic dubbing lifecycle:
/// create job → resolve video URL → call AI → track status → download/upload result.
/// </summary>
public class TranslationService
{
    private readonly IAppDbContext _db;
    private readonly IAiService _aiService;
    private readonly IStorageService _storage;
    private readonly IMapper _mapper;
    private readonly ILogger<TranslationService> _logger;
    private readonly IWebhookSettings _webhookSettings;

    public TranslationService(IAppDbContext db, IAiService aiService, IStorageService storage,
                              IMapper mapper, ILogger<TranslationService> logger,
                              IWebhookSettings webhookSettings)
    {
        _db = db;
        _aiService = aiService;
        _storage = storage;
        _mapper = mapper;
        _logger = logger;
        _webhookSettings = webhookSettings;
    }

    /// <summary>
    /// Create a translation from an existing video (by ID).
    /// </summary>
    public async Task<Result<TranslationDto>> CreateFromVideoAsync(Guid videoId, Guid userId,
                                                                    CreateTranslationRequest? options = null,
                                                                    CancellationToken ct = default)
    {
        _logger.LogInformation("TRACE CreateFromVideoAsync entered. VideoId={VideoId}, UserId={UserId}", videoId, userId);

        var video = await _db.Videos
            .FirstOrDefaultAsync(v => v.Id == videoId && v.UserId == userId, ct);

        if (video is null)
        {
            _logger.LogWarning("TRACE CreateFromVideoAsync media lookup failed before job creation. VideoId={VideoId}, UserId={UserId}", videoId, userId);
            return Result<TranslationDto>.Failure("Video not found.");
        }

        _logger.LogInformation(
            "TRACE CreateFromVideoAsync media lookup succeeded. VideoId={VideoId}, SourceType={SourceType}, HasStoragePath={HasStoragePath}, HasOriginalUrl={HasOriginalUrl}",
            video.Id, video.SourceType, video.StoragePath is not null, video.OriginalVideoUrl is not null);

        return await StartTranslationAsync(video, null, userId, options, ct);
    }

    /// <summary>
    /// Create a translation from an existing audio (by ID).
    /// </summary>
    public async Task<Result<TranslationDto>> CreateFromAudioAsync(Guid audioId, Guid userId,
                                                                    CreateTranslationRequest? options = null,
                                                                    CancellationToken ct = default)
    {
        _logger.LogInformation("TRACE CreateFromAudioAsync entered. AudioId={AudioId}, UserId={UserId}", audioId, userId);

        var audio = await _db.Audios
            .FirstOrDefaultAsync(a => a.Id == audioId && a.UserId == userId, ct);

        if (audio is null)
        {
            _logger.LogWarning("TRACE CreateFromAudioAsync media lookup failed before job creation. AudioId={AudioId}, UserId={UserId}", audioId, userId);
            return Result<TranslationDto>.Failure("Audio not found.");
        }

        _logger.LogInformation(
            "TRACE CreateFromAudioAsync media lookup succeeded. AudioId={AudioId}, SourceType={SourceType}, HasStoragePath={HasStoragePath}, HasOriginalUrl={HasOriginalUrl}",
            audio.Id, audio.SourceType, audio.StoragePath is not null, audio.OriginalAudioUrl is not null);

        return await StartTranslationAsync(null, audio, userId, options, ct);
    }

    /// <summary>
    /// Create a translation from an external URL — registers the video then starts the job.
    /// </summary>
    public async Task<Result<TranslationDto>> CreateFromUrlAsync(string videoUrl, Guid userId,
                                                                  CreateTranslationRequest? options = null,
                                                                  CancellationToken ct = default)
    {
        _logger.LogInformation("TRACE CreateFromUrlAsync entered. UserId={UserId}, VideoUrl={VideoUrl}", userId, videoUrl);

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
        _logger.LogInformation("TRACE CreateFromUrlAsync video entity added. VideoId={VideoId}", video.Id);
        var videoSaveCount = await _db.SaveChangesAsync(ct);

        _logger.LogInformation("TRACE CreateFromUrlAsync video saved. VideoId={VideoId}, SaveCount={SaveCount}", video.Id, videoSaveCount);

        return await StartTranslationAsync(video, null, userId, options, ct);
    }

    /// <summary>
    /// Handle an incoming webhook or polling update from the AI Service.
    /// IDEMPOTENT: if job is already in a terminal state, the event is ignored.
    /// </summary>
    public async Task HandleWebhookAsync(AiJobStatusDto payload, CancellationToken ct = default)
    {
        var job = await _db.TranslationJobs
            .FirstOrDefaultAsync(j => j.AiJobId == payload.JobId, ct);

        if (job is null)
        {
            _logger.LogWarning("Webhook received for unknown job: {JobId}", payload.JobId);
            return;
        }

        var liveFieldsChanged = ApplyLiveFields(job, payload);

        // IDEMPOTENCY: skip terminal duplicates, but keep any new live fields
        if (job.Status is TranslationStatus.Completed or TranslationStatus.Failed or TranslationStatus.Cancelled)
        {
            _logger.LogInformation("Ignoring duplicate webhook for job {JobId} (already {Status})",
                payload.JobId, job.Status);
            if (liveFieldsChanged)
                await _db.SaveChangesAsync(ct);
            return;
        }

        job.Progress = payload.Progress;

        switch (payload.Status)
        {
            case "completed":
                _logger.LogInformation("Job {JobId} completed. Downloading result...", payload.JobId);

                var downloadResult = await _aiService.DownloadResultAsync(payload.JobId, ct);
                if (!downloadResult.IsSuccess)
                {
                    _logger.LogError("Failed to download result for job {JobId}: {Error}",
                        payload.JobId, downloadResult.Error);
                    job.Status = TranslationStatus.Failed;
                    job.ErrorMessage = $"Download failed: {downloadResult.Error}";
                    job.CompletedAt = DateTime.UtcNow;
                    break;
                }

                await using (var stream = downloadResult.Data!)
                {
                    if (job.InputType == InputType.Audio)
                    {
                        var path = await _storage.UploadFileAsync(
                            stream,
                            $"translated_{job.Id}.wav", // Python pipeline will return .wav for audio jobs
                            $"users/{job.UserId}/results/audio", ct);
                        job.TranslatedAudioPath = path;
                        _logger.LogInformation("Job {JobId} audio result uploaded: {Path}", payload.JobId, path);
                    }
                    else
                    {
                        var path = await _storage.UploadFileAsync(
                            stream,
                            $"translated_{job.Id}.mp4",
                            $"users/{job.UserId}/results/videos", ct);
                        job.TranslatedVideoPath = path;
                        _logger.LogInformation("Job {JobId} video result uploaded: {Path}", payload.JobId, path);
                    }
                }

                job.Status = TranslationStatus.Completed;
                job.CompletedAt = DateTime.UtcNow;
                break;

            case "failed":
                job.Status = TranslationStatus.Failed;
                job.ErrorMessage = payload.ErrorMessage;
                job.CompletedAt = DateTime.UtcNow;
                _logger.LogWarning("Job {JobId} failed: {Error}", payload.JobId, payload.ErrorMessage);
                break;

            case "cancelled":
                job.Status = TranslationStatus.Cancelled;
                job.CompletedAt = DateTime.UtcNow;
                _logger.LogInformation("Job {JobId} cancelled", payload.JobId);
                break;

            default: // "processing"
                job.Status = TranslationStatus.Processing;
                break;
        }

        await _db.SaveChangesAsync(ct);
    }

    public async Task<Result<TranslationDto>> GetByIdAsync(Guid jobId, Guid userId,
                                                            CancellationToken ct = default)
    {
        var job = await _db.TranslationJobs
            .Include(j => j.Video)
            .Include(j => j.Audio)
            .FirstOrDefaultAsync(j => j.Id == jobId && j.UserId == userId, ct);

        if (job is null)
            return Result<TranslationDto>.Failure("Translation job not found.");

        var dto = _mapper.Map<TranslationDto>(job);

        if (job.TranslatedVideoPath is not null)
            dto.TranslatedVideoUrl = await _storage.GetSignedUrlAsync(job.TranslatedVideoPath, ct: ct);
            
        if (job.TranslatedAudioPath is not null)
            dto.TranslatedAudioUrl = await _storage.GetSignedUrlAsync(job.TranslatedAudioPath, ct: ct);

        return Result<TranslationDto>.Success(dto);
    }

    public async Task<Result<List<TranslationDto>>> GetAllByUserAsync(Guid userId,
                                                                       CancellationToken ct = default)
    {
        var jobs = await _db.TranslationJobs
            .Include(j => j.Video)
            .Include(j => j.Audio)
            .Where(j => j.UserId == userId)
            .OrderByDescending(j => j.CreatedAt)
            .ToListAsync(ct);

        var dtos = _mapper.Map<List<TranslationDto>>(jobs);

        foreach (var (dto, job) in dtos.Zip(jobs))
        {
            if (job.TranslatedVideoPath is not null)
                dto.TranslatedVideoUrl = await _storage.GetSignedUrlAsync(job.TranslatedVideoPath, ct: ct);
                
            if (job.TranslatedAudioPath is not null)
                dto.TranslatedAudioUrl = await _storage.GetSignedUrlAsync(job.TranslatedAudioPath, ct: ct);
        }

        return Result<List<TranslationDto>>.Success(dtos);
    }

    public async Task<Result> CancelAsync(Guid jobId, Guid userId, CancellationToken ct = default)
    {
        var job = await _db.TranslationJobs
            .FirstOrDefaultAsync(j => j.Id == jobId && j.UserId == userId, ct);

        if (job is null)
            return Result.Failure("Translation job not found.");

        if (job.Status is TranslationStatus.Completed or TranslationStatus.Failed or TranslationStatus.Cancelled)
            return Result.Failure($"Cannot cancel: job is already '{job.Status}'.");

        if (job.AiJobId is not null)
        {
            var cancelResult = await _aiService.CancelJobAsync(job.AiJobId, ct);
            if (!cancelResult.IsSuccess)
                _logger.LogWarning("AI cancel request failed for {AiJobId}: {Error}",
                    job.AiJobId, cancelResult.Error);
        }

        job.Status = TranslationStatus.Cancelled;
        job.CompletedAt = DateTime.UtcNow;
        await _db.SaveChangesAsync(ct);

        _logger.LogInformation("Translation job cancelled: {JobId}", jobId);
        return Result.Success();
    }

    // ── Private Helpers ──

    private static bool ApplyLiveFields(TranslationJob job, AiJobStatusDto payload)
    {
        var changed = false;

        if (!string.IsNullOrWhiteSpace(payload.CurrentStage) &&
            job.CurrentStage != payload.CurrentStage)
        {
            job.CurrentStage = payload.CurrentStage;
            changed = true;
        }

        if (payload.Transcript is not null && job.Transcript != payload.Transcript)
        {
            job.Transcript = payload.Transcript;
            changed = true;
        }

        if (payload.TranslatedText is not null && job.TranslatedText != payload.TranslatedText)
        {
            job.TranslatedText = payload.TranslatedText;
            changed = true;
        }

        return changed;
    }

    /// <summary>
    /// Retry a failed or cancelled job by creating a new translation for the same video.
    /// </summary>
    public async Task<Result<TranslationDto>> RetryAsync(Guid jobId, Guid userId,
                                                         CreateTranslationRequest? options = null,
                                                         CancellationToken ct = default)
    {
        var originalJob = await _db.TranslationJobs
            .Include(j => j.Video)
            .Include(j => j.Audio)
            .FirstOrDefaultAsync(j => j.Id == jobId && j.UserId == userId, ct);

        if (originalJob is null)
            return Result<TranslationDto>.Failure("Translation job not found.");

        if (originalJob.Status is not (TranslationStatus.Failed or TranslationStatus.Cancelled))
            return Result<TranslationDto>.Failure($"Cannot retry: job status is '{originalJob.Status}'. Only failed or cancelled jobs can be retried.");

        _logger.LogInformation("Retrying job {OriginalJobId} for video {VideoId}", jobId, originalJob.VideoId);

        // If no options provided by the frontend, reconstruct from the original job's saved settings
        var retryOptions = options ?? new CreateTranslationRequest
        {
            VoiceCloning = originalJob.VoiceCloning ?? true,
            BurnSubtitles = originalJob.BurnSubtitles ?? true,
            VoiceGender = originalJob.VoiceGender,
            VoiceAge = originalJob.VoiceAge,
            VoicePitch = originalJob.VoicePitch,
            VoiceStyle = originalJob.VoiceStyle,
        };

        return await StartTranslationAsync(originalJob.Video, originalJob.Audio, userId, retryOptions, ct);
    }

    // ── Private Helpers ──

    private async Task<Result<TranslationDto>> StartTranslationAsync(Video? video, Audio? audio, Guid userId,
                                                                      CreateTranslationRequest? options,
                                                                      CancellationToken ct)
    {
        if (video is null && audio is null)
        {
            _logger.LogWarning("TRACE StartTranslationAsync exited before job creation because no media was provided. UserId={UserId}", userId);
            return Result<TranslationDto>.Failure("No media provided.");
        }

        _logger.LogInformation(
            "TRACE StartTranslationAsync entered. UserId={UserId}, VideoId={VideoId}, AudioId={AudioId}",
            userId, video?.Id, audio?.Id);

        // 1. Create job record (Queued)
        var inputType = audio is not null ? InputType.Audio : InputType.Video;
        var job = new TranslationJob
        {
            VideoId = video?.Id,
            AudioId = audio?.Id,
            Video = video,
            Audio = audio,
            InputType = inputType,
            OutputType = inputType == InputType.Audio ? OutputType.Audio : OutputType.Video,
            UserId = userId,
            Status = TranslationStatus.Queued,
            VoiceCloning = options?.VoiceCloning,
            BurnSubtitles = options?.BurnSubtitles,
            VoiceGender = options?.VoiceGender,
            VoiceAge = options?.VoiceAge,
            VoicePitch = options?.VoicePitch,
            VoiceStyle = options?.VoiceStyle,
        };

        _logger.LogInformation(
            "TRACE TranslationJob created in memory. JobId={JobId}, InputType={InputType}, OutputType={OutputType}, Status={Status}, VideoId={VideoId}, AudioId={AudioId}",
            job.Id, job.InputType, job.OutputType, job.Status, job.VideoId, job.AudioId);

        _db.TranslationJobs.Add(job);
        _logger.LogInformation("TRACE TranslationJobs.Add executed. JobId={JobId}", job.Id);

        var firstSaveCount = await _db.SaveChangesAsync(ct);
        _logger.LogInformation("TRACE TranslationJob first SaveChangesAsync completed. JobId={JobId}, SaveCount={SaveCount}", job.Id, firstSaveCount);

        try
        {
            // 2. Resolve the URL for the AI Service
            string urlForAi;
            if (video is not null)
            {
                if (video.SourceType == VideoSourceType.Uploaded && video.StoragePath is not null)
                {
                    _logger.LogInformation("TRACE Generating signed URL for video job. JobId={JobId}, StoragePath={StoragePath}", job.Id, video.StoragePath);
                    urlForAi = await _storage.GetSignedUrlAsync(video.StoragePath, expiresInSeconds: 7200, ct: ct);
                    _logger.LogInformation("TRACE Signed URL generated for video job. JobId={JobId}", job.Id);
                }
                else if (video.SourceType == VideoSourceType.ExternalUrl && video.OriginalVideoUrl is not null)
                {
                    urlForAi = video.OriginalVideoUrl;
                    _logger.LogInformation("TRACE External video URL selected for AI job. JobId={JobId}", job.Id);
                }
                else
                {
                    _logger.LogWarning("TRACE Video has no accessible URL after job creation. JobId={JobId}, VideoId={VideoId}", job.Id, video.Id);
                    return await MarkJobAsFailedAsync(job, "Video has no accessible URL.", ct);
                }
            }
            else
            {
                if (audio!.StoragePath is not null)
                {
                    _logger.LogInformation("TRACE Generating signed URL for audio job. JobId={JobId}, StoragePath={StoragePath}", job.Id, audio.StoragePath);
                    urlForAi = await _storage.GetSignedUrlAsync(audio.StoragePath, expiresInSeconds: 7200, ct: ct);
                    _logger.LogInformation("TRACE Signed URL generated for audio job. JobId={JobId}", job.Id);
                }
                else if (audio.OriginalAudioUrl is not null)
                {
                    urlForAi = audio.OriginalAudioUrl;
                    _logger.LogInformation("TRACE External audio URL selected for AI job. JobId={JobId}", job.Id);
                }
                else
                {
                    _logger.LogWarning("TRACE Audio has no accessible URL after job creation. JobId={JobId}, AudioId={AudioId}", job.Id, audio.Id);
                    return await MarkJobAsFailedAsync(job, "Audio has no accessible URL.", ct);
                }
            }

            // 3. Call the AI Service
            var webhookUrl = _webhookSettings.WebhookCallbackUrl;
            
            // Let the AI service know it's audio.
            if (options is not null)
                options.InputType = inputType;
            
            _logger.LogInformation("TRACE AI StartJobAsync starting. JobId={JobId}, InputType={InputType}", job.Id, inputType);
            var startResult = await _aiService.StartJobAsync(urlForAi, webhookUrl, options, ct);

            if (!startResult.IsSuccess)
            {
                _logger.LogError("Failed to start AI job for job {JobId}: {Error}", job.Id, startResult.Error);
                return await MarkJobAsFailedAsync(job, $"AI Service error: {startResult.Error}", ct);
            }

            // 4. Update with AI job ID
            job.AiJobId = startResult.Data;
            job.Status = TranslationStatus.Processing;
            var processingSaveCount = await _db.SaveChangesAsync(ct);

            _logger.LogInformation(
                "TRACE AI job started and TranslationJob updated. JobId={JobId}, AiJobId={AiJobId}, SaveCount={SaveCount}",
                job.Id, startResult.Data, processingSaveCount);

            var dto = _mapper.Map<TranslationDto>(job);
            return Result<TranslationDto>.Success(dto);
        }
        catch (OperationCanceledException) when (ct.IsCancellationRequested)
        {
            throw;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Translation job {JobId} failed before AI processing could start", job.Id);
            return await MarkJobAsFailedAsync(job, $"AI Service error: {ex.Message}", CancellationToken.None);
        }
    }

    private async Task<Result<TranslationDto>> MarkJobAsFailedAsync(TranslationJob job, string errorMessage, CancellationToken ct)
    {
        _logger.LogInformation("TRACE MarkJobAsFailedAsync entered. JobId={JobId}, ErrorMessage={ErrorMessage}", job.Id, errorMessage);
        job.Status = TranslationStatus.Failed;
        job.ErrorMessage = errorMessage;
        job.CompletedAt = DateTime.UtcNow;
        var failedSaveCount = await _db.SaveChangesAsync(ct);
        _logger.LogInformation("TRACE Failed TranslationJob saved. JobId={JobId}, SaveCount={SaveCount}", job.Id, failedSaveCount);
        var dto = _mapper.Map<TranslationDto>(job);
        return Result<TranslationDto>.Success(dto);
    }
}
