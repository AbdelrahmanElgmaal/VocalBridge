using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using VocalBridge.Domain.Enums;
using VocalBridge.Application.Interfaces;
using VocalBridge.Application.Services;

namespace VocalBridge.API.Controllers;

[ApiController]
[Route("api/[controller]")]
[Authorize]
public class AudiosController : ControllerBase
{
    private readonly AudioService _audioService;
    private readonly ICurrentUserService _currentUser;

    public AudiosController(AudioService audioService, ICurrentUserService currentUser)
    {
        _audioService = audioService;
        _currentUser = currentUser;
    }

    /// <summary>Upload a local audio file (mp3, wav, m4a). Max 10 MB. Max 25 seconds.</summary>
    [HttpPost("upload")]
    [RequestSizeLimit(10_000_000)]
    public async Task<IActionResult> Upload(IFormFile file, [FromForm] string? sourceType, CancellationToken ct)
    {
        if (file is null || file.Length == 0)
            return BadRequest(new { error = "No file uploaded." });

        var userId = _currentUser.GetUserId();
        using var stream = file.OpenReadStream();
        
        if (!Enum.TryParse<AudioSourceType>(sourceType, true, out var parsedSourceType))
            parsedSourceType = AudioSourceType.Uploaded;

        var result = await _audioService.UploadAsync(
            stream, file.FileName, file.ContentType, file.Length, parsedSourceType, userId, ct);

        return result.IsSuccess
            ? CreatedAtAction(nameof(GetById), new { id = result.Data!.Id }, result.Data)
            : BadRequest(new { error = result.Error });
    }

    /// <summary>Get all audios for the current user.</summary>
    [HttpGet]
    public async Task<IActionResult> GetAll(CancellationToken ct)
    {
        var userId = _currentUser.GetUserId();
        var result = await _audioService.GetAllByUserAsync(userId, ct);
        return Ok(result.Data);
    }

    /// <summary>Get a single audio by ID (with signed URL).</summary>
    [HttpGet("{id:guid}")]
    public async Task<IActionResult> GetById(Guid id, CancellationToken ct)
    {
        var userId = _currentUser.GetUserId();
        var result = await _audioService.GetByIdAsync(id, userId, ct);
        return result.IsSuccess ? Ok(result.Data) : NotFound(new { error = result.Error });
    }

    /// <summary>Delete an audio, its storage files, and associated translation results.</summary>
    [HttpDelete("{id:guid}")]
    public async Task<IActionResult> Delete(Guid id, CancellationToken ct)
    {
        var userId = _currentUser.GetUserId();
        var result = await _audioService.DeleteAsync(id, userId, ct);
        return result.IsSuccess ? NoContent() : NotFound(new { error = result.Error });
    }
}
