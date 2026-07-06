namespace VocalBridge.Application.Interfaces;

/// <summary>
/// Provides webhook configuration to Application services.
/// Implemented in Infrastructure using IOptions&lt;AiServiceSettings&gt;.
/// Avoids Application depending on Infrastructure configuration.
/// </summary>
public interface IWebhookSettings
{
    string WebhookCallbackUrl { get; }
    string WebhookSecret { get; }
}
