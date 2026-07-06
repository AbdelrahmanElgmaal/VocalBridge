using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using VocalBridge.Application.Interfaces;
using VocalBridge.Application.Services;
using VocalBridge.Domain.Enums;

namespace VocalBridge.Infrastructure.BackgroundJobs;

/// <summary>
/// Background polling worker — safety net for lost webhooks.
/// Polls in batches of 50 to avoid memory issues.
/// </summary>
public class AiJobPollingWorker : BackgroundService
{
    private readonly IServiceScopeFactory _scopeFactory;
    private readonly ILogger<AiJobPollingWorker> _logger;
    private readonly TimeSpan _interval = TimeSpan.FromSeconds(60);
    private const int BatchSize = 50;

    public AiJobPollingWorker(IServiceScopeFactory scopeFactory, ILogger<AiJobPollingWorker> logger)
    {
        _scopeFactory = scopeFactory;
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        _logger.LogInformation("AI Job Polling Worker started. Interval: {Interval}s, Batch: {Batch}",
            _interval.TotalSeconds, BatchSize);

        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                await PollPendingJobsAsync(stoppingToken);
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
            {
                break; // Graceful shutdown
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error during AI job polling cycle");
            }

            await Task.Delay(_interval, stoppingToken);
        }

        _logger.LogInformation("AI Job Polling Worker stopped");
    }

    private async Task PollPendingJobsAsync(CancellationToken ct)
    {
        using var scope = _scopeFactory.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<IAppDbContext>();
        var aiService = scope.ServiceProvider.GetRequiredService<IAiService>();
        var translationService = scope.ServiceProvider.GetRequiredService<TranslationService>();

        // Batch processing — only load up to BatchSize jobs at a time
        var activeJobs = await db.TranslationJobs
            .Where(j => j.Status == TranslationStatus.Processing && j.AiJobId != null)
            .OrderBy(j => j.CreatedAt)
            .Take(BatchSize)
            .ToListAsync(ct);

        if (activeJobs.Count == 0) return;

        _logger.LogInformation("Polling {Count} active job(s)", activeJobs.Count);

        foreach (var job in activeJobs)
        {
            if (ct.IsCancellationRequested) break;

            try
            {
                var statusResult = await aiService.GetStatusAsync(job.AiJobId!, ct);

                if (!statusResult.IsSuccess)
                {
                    _logger.LogWarning("Failed to poll job {AiJobId}: {Error}",
                        job.AiJobId, statusResult.Error);
                    continue;
                }

                var status = statusResult.Data!;

                if (status.Status is "completed" or "failed" or "cancelled")
                {
                    _logger.LogInformation("Poller detected status change: {AiJobId} → {Status}",
                        job.AiJobId, status.Status);
                }

                await translationService.HandleWebhookAsync(status, ct);
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Failed to poll job {AiJobId}", job.AiJobId);
            }
        }
    }
}
