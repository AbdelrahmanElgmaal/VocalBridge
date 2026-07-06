namespace VocalBridge.Infrastructure.AI.Settings;

/// <summary>
/// AI Service configuration bound from appsettings.json → "AiService" section.
/// </summary>
public class AiServiceSettings
{
    public string BaseUrl { get; set; } = "http://localhost:8000";
    public string WebhookSecret { get; set; } = string.Empty;
    public string WebhookCallbackUrl { get; set; } = string.Empty;
    public int TimeoutSeconds { get; set; } = 30;
}
