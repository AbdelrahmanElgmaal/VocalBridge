using VocalBridge.Domain.Common;

namespace VocalBridge.Domain.Entities;

/// <summary>
/// Represents a stored refresh token for JWT rotation.
/// Each user can have multiple active refresh tokens (e.g., from different devices).
/// </summary>
public class RefreshToken : BaseEntity
{
    public Guid UserId { get; set; }
    public string Token { get; set; } = string.Empty;
    public DateTime ExpiresAt { get; set; }
    public DateTime? RevokedAt { get; set; }

    // ── Computed Properties ──
    public bool IsExpired => DateTime.UtcNow >= ExpiresAt;
    public bool IsRevoked => RevokedAt is not null;
    public bool IsActive => !IsExpired && !IsRevoked;

    // ── Navigation ──
    public User User { get; set; } = null!;
}
