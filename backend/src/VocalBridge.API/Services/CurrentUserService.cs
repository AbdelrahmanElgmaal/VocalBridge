using System.Security.Claims;
using VocalBridge.Application.Interfaces;

namespace VocalBridge.API.Services;

/// <summary>
/// Reads the authenticated user's ID from the JWT claims in HttpContext.
/// Registered as Scoped so it has access to the current request's context.
/// </summary>
public class CurrentUserService : ICurrentUserService
{
    private readonly IHttpContextAccessor _httpContextAccessor;

    public CurrentUserService(IHttpContextAccessor httpContextAccessor)
    {
        _httpContextAccessor = httpContextAccessor;
    }

    public Guid GetUserId()
    {
        var claim = _httpContextAccessor.HttpContext?.User
            .FindFirst(ClaimTypes.NameIdentifier)
            ?? _httpContextAccessor.HttpContext?.User
                .FindFirst("sub");

        if (claim is null || !Guid.TryParse(claim.Value, out var userId))
            throw new UnauthorizedAccessException("User is not authenticated.");

        return userId;
    }
}
