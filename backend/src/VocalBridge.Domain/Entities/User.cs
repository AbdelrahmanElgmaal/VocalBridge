using VocalBridge.Domain.Common;

namespace VocalBridge.Domain.Entities;

/// <summary>
/// Represents a registered user of the Vocal Bridge platform.
/// </summary>
public class User : BaseEntity
{
    public string FullName { get; set; } = string.Empty;
    public string Email { get; set; } = string.Empty;
    public string PasswordHash { get; set; } = string.Empty;

    // ── Navigation Properties ──
    public ICollection<Video> Videos { get; set; } = new List<Video>();
    public ICollection<RefreshToken> RefreshTokens { get; set; } = new List<RefreshToken>();
}
