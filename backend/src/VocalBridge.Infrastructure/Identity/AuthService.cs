using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;
using VocalBridge.Application.Common;
using VocalBridge.Application.DTOs.Auth;
using VocalBridge.Application.Interfaces;
using VocalBridge.Domain.Entities;

namespace VocalBridge.Infrastructure.Identity;

/// <summary>
/// Implements IAuthService — registration, login, and token rotation
/// using BCrypt for password hashing and custom JWT generation.
/// </summary>
public class AuthService : IAuthService
{
    private readonly IAppDbContext _db;
    private readonly JwtProvider _jwt;
    private readonly ILogger<AuthService> _logger;

    public AuthService(IAppDbContext db, JwtProvider jwt, ILogger<AuthService> logger)
    {
        _db = db;
        _jwt = jwt;
        _logger = logger;
    }

    public async Task<Result<AuthResponse>> RegisterAsync(RegisterRequest request,
                                                           CancellationToken ct = default)
    {
        var normalizedEmail = request.Email.Trim().ToLowerInvariant();

        var exists = await _db.Users.AnyAsync(u => u.Email == normalizedEmail, ct);
        if (exists)
            return Result<AuthResponse>.Failure("An account with this email already exists.");

        var user = new User
        {
            FullName = request.FullName.Trim(),
            Email = normalizedEmail,
            PasswordHash = BCrypt.Net.BCrypt.HashPassword(request.Password)
        };

        _db.Users.Add(user);

        var accessToken = _jwt.GenerateAccessToken(user);
        var refreshToken = CreateRefreshToken(user.Id);
        _db.RefreshTokens.Add(refreshToken);

        await _db.SaveChangesAsync(ct);

        _logger.LogInformation("User registered: {UserId} ({Email})", user.Id, normalizedEmail);

        return Result<AuthResponse>.Success(new AuthResponse
        {
            AccessToken = accessToken,
            RefreshToken = refreshToken.Token,
            ExpiresAt = _jwt.GetAccessTokenExpiration()
        });
    }

    public async Task<Result<AuthResponse>> LoginAsync(LoginRequest request,
                                                        CancellationToken ct = default)
    {
        var normalizedEmail = request.Email.Trim().ToLowerInvariant();

        var user = await _db.Users
            .FirstOrDefaultAsync(u => u.Email == normalizedEmail, ct);

        if (user is null || !BCrypt.Net.BCrypt.Verify(request.Password, user.PasswordHash))
        {
            _logger.LogWarning("Failed login attempt for: {Email}", normalizedEmail);
            return Result<AuthResponse>.Failure("Invalid email or password.");
        }

        var accessToken = _jwt.GenerateAccessToken(user);
        var refreshToken = CreateRefreshToken(user.Id);
        _db.RefreshTokens.Add(refreshToken);

        await _db.SaveChangesAsync(ct);

        _logger.LogInformation("User logged in: {UserId}", user.Id);

        return Result<AuthResponse>.Success(new AuthResponse
        {
            AccessToken = accessToken,
            RefreshToken = refreshToken.Token,
            ExpiresAt = _jwt.GetAccessTokenExpiration()
        });
    }

    public async Task<Result<AuthResponse>> RefreshTokenAsync(RefreshTokenRequest request,
                                                               CancellationToken ct = default)
    {
        var storedToken = await _db.RefreshTokens
            .Include(rt => rt.User)
            .FirstOrDefaultAsync(rt => rt.Token == request.RefreshToken, ct);

        if (storedToken is null || !storedToken.IsActive)
            return Result<AuthResponse>.Failure("Invalid or expired refresh token.");

        storedToken.RevokedAt = DateTime.UtcNow;

        var user = storedToken.User;
        var newAccessToken = _jwt.GenerateAccessToken(user);
        var newRefreshToken = CreateRefreshToken(user.Id);
        _db.RefreshTokens.Add(newRefreshToken);

        await _db.SaveChangesAsync(ct);

        return Result<AuthResponse>.Success(new AuthResponse
        {
            AccessToken = newAccessToken,
            RefreshToken = newRefreshToken.Token,
            ExpiresAt = _jwt.GetAccessTokenExpiration()
        });
    }

    public async Task<Result> RevokeTokenAsync(Guid userId, string refreshToken,
                                                CancellationToken ct = default)
    {
        var storedToken = await _db.RefreshTokens
            .FirstOrDefaultAsync(rt => rt.Token == refreshToken && rt.UserId == userId, ct);

        if (storedToken is null)
            return Result.Failure("Token not found.");

        storedToken.RevokedAt = DateTime.UtcNow;
        await _db.SaveChangesAsync(ct);

        _logger.LogInformation("Refresh token revoked for user {UserId}", userId);
        return Result.Success();
    }

    private RefreshToken CreateRefreshToken(Guid userId) => new()
    {
        UserId = userId,
        Token = _jwt.GenerateRefreshToken(),
        ExpiresAt = _jwt.GetRefreshTokenExpiration()
    };
}
