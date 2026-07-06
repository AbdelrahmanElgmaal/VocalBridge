using System.Security.Cryptography;
using System.Text;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Options;
using VocalBridge.Application.DTOs.Translations;
using VocalBridge.Application.Services;
using VocalBridge.Infrastructure.AI.Settings;

namespace VocalBridge.API.Controllers;

/// <summary>
/// Receives webhook POST notifications from the external AI Service.
/// Secured with a shared secret using timing-safe comparison.
/// </summary>
[ApiController]
[Route("api/webhooks")]
public class WebhooksController : ControllerBase
{
    private readonly TranslationService _translationService;
    private readonly string _webhookSecret;
    private readonly ILogger<WebhooksController> _logger;

    public WebhooksController(
        TranslationService translationService,
        IOptions<AiServiceSettings> settings,
        ILogger<WebhooksController> logger)
    {
        _translationService = translationService;
        _webhookSecret = settings.Value.WebhookSecret;
        _logger = logger;
    }

    /// <summary>Receive AI Service status update webhook.</summary>
    [HttpPost("ai-status")]
    public async Task<IActionResult> HandleAiWebhook(
        [FromHeader(Name = "X-Webhook-Secret")] string? secret,
        [FromBody] AiJobStatusDto payload,
        CancellationToken ct)
    {
        // Timing-safe secret comparison — prevents timing attacks
        if (string.IsNullOrEmpty(_webhookSecret) || string.IsNullOrEmpty(secret) ||
            !CryptographicOperations.FixedTimeEquals(
                Encoding.UTF8.GetBytes(_webhookSecret),
                Encoding.UTF8.GetBytes(secret)))
        {
            _logger.LogWarning("Webhook rejected — invalid or missing secret");
            return Unauthorized();
        }

        _logger.LogInformation(
            "Webhook received: job={JobId} status={Status} progress={Progress}%",
            payload.JobId, payload.Status, payload.Progress);

        await _translationService.HandleWebhookAsync(payload, ct);

        return Ok();
    }
}
