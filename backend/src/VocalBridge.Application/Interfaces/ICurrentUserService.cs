namespace VocalBridge.Application.Interfaces;

/// <summary>
/// Provides the authenticated user's identity.
/// Implemented in the API layer (reads JWT claims from HttpContext).
/// </summary>
public interface ICurrentUserService
{
    Guid GetUserId();
}
