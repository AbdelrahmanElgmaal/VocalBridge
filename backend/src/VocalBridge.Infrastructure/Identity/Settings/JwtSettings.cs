namespace VocalBridge.Infrastructure.Identity.Settings;

/// <summary>
/// JWT configuration bound from appsettings.json → "Jwt" section.
/// </summary>
public class JwtSettings
{
    public string SecretKey { get; set; } = string.Empty;
    public string Issuer { get; set; } = "VocalBridge";
    public string Audience { get; set; } = "VocalBridge";
    public int AccessTokenExpirationMinutes { get; set; } = 30;
    public int RefreshTokenExpirationDays { get; set; } = 7;
}
