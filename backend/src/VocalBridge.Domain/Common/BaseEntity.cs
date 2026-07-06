namespace VocalBridge.Domain.Common;

/// <summary>
/// Base class for all domain entities.
/// Provides a primary key and creation timestamp.
/// </summary>
public abstract class BaseEntity
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
}
