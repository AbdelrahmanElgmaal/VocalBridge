using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using VocalBridge.Application.Interfaces;
using VocalBridge.Application.Services;

namespace VocalBridge.API.Controllers;

[ApiController]
[Route("api/[controller]")]
[Authorize]
public class VideosController : ControllerBase
{
    private readonly VideoService _videoService;
    private readonly ICurrentUserService _currentUser;

    public VideosController(VideoService videoService, ICurrentUserService currentUser)
    {
        _videoService = videoService;
        _currentUser = currentUser;
    }

    /// <summary>Upload a local video file (mp4, mov, avi, mkv, webm, wmv, flv). Max 500 MB.</summary>
    [HttpPost("upload")]
    [RequestSizeLimit(500_000_000)]
    public async Task<IActionResult> Upload(IFormFile file, CancellationToken ct)
    {
        if (file is null || file.Length == 0)
            return BadRequest(new { error = "No file uploaded." });

        var userId = _currentUser.GetUserId();
        using var stream = file.OpenReadStream();
        var result = await _videoService.UploadAsync(
            stream, file.FileName, file.ContentType, file.Length, userId, ct);

        return result.IsSuccess
            ? CreatedAtAction(nameof(GetById), new { id = result.Data!.Id }, result.Data)
            : BadRequest(new { error = result.Error });
    }

    /// <summary>Get all videos for the current user.</summary>
    [HttpGet]
    public async Task<IActionResult> GetAll(CancellationToken ct)
    {
        var userId = _currentUser.GetUserId();
        var result = await _videoService.GetAllByUserAsync(userId, ct);
        return Ok(result.Data);
    }

    /// <summary>Get a single video by ID (with signed URL for uploaded videos).</summary>
    [HttpGet("{id:guid}")]
    public async Task<IActionResult> GetById(Guid id, CancellationToken ct)
    {
        var userId = _currentUser.GetUserId();
        var result = await _videoService.GetByIdAsync(id, userId, ct);
        return result.IsSuccess ? Ok(result.Data) : NotFound(new { error = result.Error });
    }

    /// <summary>Delete a video, its storage files, and associated translation results.</summary>
    [HttpDelete("{id:guid}")]
    public async Task<IActionResult> Delete(Guid id, CancellationToken ct)
    {
        var userId = _currentUser.GetUserId();
        var result = await _videoService.DeleteAsync(id, userId, ct);
        return result.IsSuccess ? NoContent() : NotFound(new { error = result.Error });
    }
}
