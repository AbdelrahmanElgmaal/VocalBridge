using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using VocalBridge.Application.Interfaces;

namespace VocalBridge.API.Controllers;

/// <summary>
/// Health check endpoint — reports connectivity status for all external dependencies.
/// No authentication required.
/// </summary>
[ApiController]
[Route("api/[controller]")]
public class HealthController : ControllerBase
{
    private readonly IAppDbContext _db;
    private readonly IStorageService _storage;
    private readonly IAiService _aiService;

    public HealthController(IAppDbContext db, IStorageService storage, IAiService aiService)
    {
        _db = db;
        _storage = storage;
        _aiService = aiService;
    }

    /// <summary>Check the health of all external dependencies.</summary>
    [HttpGet]
    public async Task<IActionResult> Get(CancellationToken ct)
    {
        var sqlHealthy = await CheckSqlAsync(ct);
        var supabaseHealthy = await _storage.IsHealthyAsync(ct);
        var aiHealthy = await _aiService.IsHealthyAsync(ct);

        var isAllHealthy = sqlHealthy && supabaseHealthy && aiHealthy;

        var result = new
        {
            status = isAllHealthy ? "healthy" : "degraded",
            services = new
            {
                sqlServer = sqlHealthy ? "healthy" : "unhealthy",
                supabase = supabaseHealthy ? "healthy" : "unhealthy",
                aiService = aiHealthy ? "healthy" : "unhealthy"
            },
            timestamp = DateTime.UtcNow
        };

        return isAllHealthy ? Ok(result) : StatusCode(503, result);
    }

    private async Task<bool> CheckSqlAsync(CancellationToken ct)
    {
        try
        {
            await _db.Users.Select(u => 1).FirstOrDefaultAsync(ct);
            return true;
        }
        catch
        {
            return false;
        }
    }
}
