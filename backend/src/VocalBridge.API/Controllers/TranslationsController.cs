using FluentValidation;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using VocalBridge.Application.DTOs.Translations;
using VocalBridge.Application.Interfaces;
using VocalBridge.Application.Services;
using VocalBridge.Application.Common;

namespace VocalBridge.API.Controllers;

[ApiController]
[Route("api/[controller]")]
[Authorize]
public class TranslationsController : ControllerBase
{
    private readonly TranslationService _translationService;
    private readonly ICurrentUserService _currentUser;
    private readonly IValidator<CreateTranslationRequest> _validator;
    private readonly ILogger<TranslationsController> _logger;

    public TranslationsController(
        TranslationService translationService,
        ICurrentUserService currentUser,
        IValidator<CreateTranslationRequest> validator,
        ILogger<TranslationsController> logger)
    {
        _translationService = translationService;
        _currentUser = currentUser;
        _validator = validator;
        _logger = logger;
    }

    /// <summary>
    /// Start a new English → Arabic translation job.
    /// Provide exactly ONE source: VideoId, VideoUrl, or AudioId.
    /// </summary>
    [HttpPost]
    public async Task<IActionResult> Create(CreateTranslationRequest request, CancellationToken ct)
    {
        _logger.LogInformation(
            "TRACE Translation create request entered. VideoId={VideoId}, AudioId={AudioId}, HasVideoUrl={HasVideoUrl}, InputType={InputType}",
            request.VideoId, request.AudioId, !string.IsNullOrWhiteSpace(request.VideoUrl), request.InputType);

        var validation = await _validator.ValidateAsync(request, ct);
        if (!validation.IsValid)
        {
            _logger.LogWarning(
                "TRACE Translation create validation failed. Errors={Errors}",
                string.Join("; ", validation.Errors.Select(e => $"{e.PropertyName}:{e.ErrorMessage}")));
            throw new ValidationException(validation.Errors);
        }

        _logger.LogInformation("TRACE Translation create validation passed.");

        var userId = _currentUser.GetUserId();
        _logger.LogInformation("TRACE Translation create current user resolved. UserId={UserId}", userId);

        Result<TranslationDto> result;

        if (request.AudioId.HasValue)
        {
            _logger.LogInformation("TRACE Translation create dispatching to CreateFromAudioAsync. AudioId={AudioId}", request.AudioId.Value);
            result = await _translationService.CreateFromAudioAsync(request.AudioId.Value, userId, request, ct);
        }
        else if (request.VideoId.HasValue)
        {
            _logger.LogInformation("TRACE Translation create dispatching to CreateFromVideoAsync. VideoId={VideoId}", request.VideoId.Value);
            result = await _translationService.CreateFromVideoAsync(request.VideoId.Value, userId, request, ct);
        }
        else
        {
            _logger.LogInformation("TRACE Translation create dispatching to CreateFromUrlAsync. VideoUrl={VideoUrl}", request.VideoUrl);
            result = await _translationService.CreateFromUrlAsync(request.VideoUrl!, userId, request, ct);
        }

        _logger.LogInformation(
            "TRACE Translation create service returned. IsSuccess={IsSuccess}, JobId={JobId}, Error={Error}",
            result.IsSuccess, result.Data?.Id, result.Error);

        return result.IsSuccess
            ? CreatedAtAction(nameof(GetById), new { id = result.Data!.Id }, result.Data)
            : BadRequest(new { error = result.Error });
    }

    /// <summary>Get all translation jobs for the current user (history).</summary>
    [HttpGet]
    public async Task<IActionResult> GetAll(CancellationToken ct)
    {
        var userId = _currentUser.GetUserId();
        var result = await _translationService.GetAllByUserAsync(userId, ct);
        return Ok(result.Data);
    }

    /// <summary>Get a single translation job by ID.</summary>
    [HttpGet("{id:guid}")]
    public async Task<IActionResult> GetById(Guid id, CancellationToken ct)
    {
        var userId = _currentUser.GetUserId();
        var result = await _translationService.GetByIdAsync(id, userId, ct);
        return result.IsSuccess ? Ok(result.Data) : NotFound(new { error = result.Error });
    }

    /// <summary>Cancel a running translation job.</summary>
    [HttpPost("{id:guid}/cancel")]
    public async Task<IActionResult> Cancel(Guid id, CancellationToken ct)
    {
        var userId = _currentUser.GetUserId();
        var result = await _translationService.CancelAsync(id, userId, ct);
        return result.IsSuccess
            ? Ok(new { message = "Job cancelled successfully." })
            : BadRequest(new { error = result.Error });
    }

    /// <summary>Retry a failed or cancelled translation job using the same video.</summary>
    [HttpPost("{id:guid}/retry")]
    public async Task<IActionResult> Retry(Guid id, [FromBody] CreateTranslationRequest? options, CancellationToken ct)
    {
        var userId = _currentUser.GetUserId();
        var result = await _translationService.RetryAsync(id, userId, options, ct);
        return result.IsSuccess
            ? CreatedAtAction(nameof(GetById), new { id = result.Data!.Id }, result.Data)
            : BadRequest(new { error = result.Error });
    }
}
