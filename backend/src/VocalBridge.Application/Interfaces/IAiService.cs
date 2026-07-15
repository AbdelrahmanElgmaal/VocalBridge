using VocalBridge.Application.Common;
using VocalBridge.Application.DTOs.Translations;

namespace VocalBridge.Application.Interfaces;

/// <summary>
/// Abstracts communication with the external AI Dubbing Service.
/// Language is hardcoded: English → Arabic. No language selection.
/// Returns Result&lt;T&gt; instead of throwing on infrastructure errors.
/// </summary>
public interface IAiService
{
    /// <summary>
    /// Start a new English → Arabic dubbing job.
    /// Returns the AI-assigned job ID wrapped in Result.
    /// </summary>
    Task<Result<string>> StartJobAsync(string videoUrl, string? webhookUrl,
                                       CreateTranslationRequest? options = null,
                                       CancellationToken ct = default);

    /// <summary>Get the current status of an AI job.</summary>
    Task<Result<AiJobStatusDto>> GetStatusAsync(string aiJobId, CancellationToken ct = default);

    /// <summary>Cancel a running AI job.</summary>
    Task<Result> CancelJobAsync(string aiJobId, CancellationToken ct = default);

    /// <summary>Download the translated Arabic media as a stream.</summary>
    Task<Result<Stream>> DownloadResultAsync(string aiJobId, bool isAudio = false, CancellationToken ct = default);

    /// <summary>Check if the AI service is reachable.</summary>
    Task<bool> IsHealthyAsync(CancellationToken ct = default);
}
