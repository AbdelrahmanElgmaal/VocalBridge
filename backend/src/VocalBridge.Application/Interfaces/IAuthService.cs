using VocalBridge.Application.Common;
using VocalBridge.Application.DTOs.Auth;

namespace VocalBridge.Application.Interfaces;

/// <summary>
/// Handles user registration, login, and JWT token management.
/// Implemented in Infrastructure using BCrypt + JWT.
/// </summary>
public interface IAuthService
{
    Task<Result<AuthResponse>> RegisterAsync(RegisterRequest request, CancellationToken ct = default);
    Task<Result<AuthResponse>> LoginAsync(LoginRequest request, CancellationToken ct = default);
    Task<Result<AuthResponse>> RefreshTokenAsync(RefreshTokenRequest request, CancellationToken ct = default);
    Task<Result> RevokeTokenAsync(Guid userId, string refreshToken, CancellationToken ct = default);
}
