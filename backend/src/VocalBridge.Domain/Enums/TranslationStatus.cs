namespace VocalBridge.Domain.Enums;

/// <summary>
/// Represents the lifecycle states of a translation job.
/// Maps directly to the AI Service's status contract.
/// </summary>
public enum TranslationStatus
{
    /// <summary>Job created, not yet sent to the AI Service.</summary>
    Queued = 0,

    /// <summary>AI Service is actively processing the video.</summary>
    Processing = 1,

    /// <summary>Translation completed successfully. Dubbed video is available.</summary>
    Completed = 2,

    /// <summary>AI Service reported an error during processing.</summary>
    Failed = 3,

    /// <summary>Job was cancelled by the user or the system.</summary>
    Cancelled = 4
}
