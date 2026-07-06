using Microsoft.Extensions.Options;
using VocalBridge.Application.Interfaces;
using VocalBridge.Infrastructure.AI.Settings;

namespace VocalBridge.Infrastructure.AI;

/// <summary>
/// Adapts AiServiceSettings into the IWebhookSettings interface
/// so Application services can access webhook config without
/// depending on Infrastructure configuration classes.
/// </summary>
public class WebhookSettingsAdapter : IWebhookSettings
{
    private readonly AiServiceSettings _settings;

    public WebhookSettingsAdapter(IOptions<AiServiceSettings> settings)
    {
        _settings = settings.Value;
    }

    public string WebhookCallbackUrl => _settings.WebhookCallbackUrl;
    public string WebhookSecret => _settings.WebhookSecret;
}
