using FluentValidation;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using VocalBridge.Application.DTOs.Auth;
using VocalBridge.Application.Interfaces;

namespace VocalBridge.API.Controllers;

[ApiController]
[Route("api/[controller]")]
public class AuthController : ControllerBase
{
    private readonly IAuthService _authService;
    private readonly ICurrentUserService _currentUser;
    private readonly IValidator<RegisterRequest> _registerValidator;
    private readonly IValidator<LoginRequest> _loginValidator;

    public AuthController(
        IAuthService authService,
        ICurrentUserService currentUser,
        IValidator<RegisterRequest> registerValidator,
        IValidator<LoginRequest> loginValidator)
    {
        _authService = authService;
        _currentUser = currentUser;
        _registerValidator = registerValidator;
        _loginValidator = loginValidator;
    }

    /// <summary>Register a new account.</summary>
    [HttpPost("register")]
    [AllowAnonymous]
    public async Task<IActionResult> Register(RegisterRequest request, CancellationToken ct)
    {
        var validation = await _registerValidator.ValidateAsync(request, ct);
        if (!validation.IsValid)
            throw new ValidationException(validation.Errors);

        var result = await _authService.RegisterAsync(request, ct);
        return result.IsSuccess ? Ok(result.Data) : BadRequest(new { error = result.Error });
    }

    /// <summary>Login with email and password.</summary>
    [HttpPost("login")]
    [AllowAnonymous]
    public async Task<IActionResult> Login(LoginRequest request, CancellationToken ct)
    {
        var validation = await _loginValidator.ValidateAsync(request, ct);
        if (!validation.IsValid)
            throw new ValidationException(validation.Errors);

        var result = await _authService.LoginAsync(request, ct);
        return result.IsSuccess ? Ok(result.Data) : Unauthorized(new { error = result.Error });
    }

    /// <summary>Rotate tokens — exchange a valid refresh token for new tokens.</summary>
    [HttpPost("refresh")]
    [AllowAnonymous]
    public async Task<IActionResult> Refresh(RefreshTokenRequest request, CancellationToken ct)
    {
        var result = await _authService.RefreshTokenAsync(request, ct);
        return result.IsSuccess ? Ok(result.Data) : Unauthorized(new { error = result.Error });
    }

    /// <summary>Revoke a refresh token (logout).</summary>
    [HttpPost("revoke")]
    [Authorize]
    public async Task<IActionResult> Revoke(RefreshTokenRequest request, CancellationToken ct)
    {
        var userId = _currentUser.GetUserId();
        var result = await _authService.RevokeTokenAsync(userId, request.RefreshToken, ct);
        return result.IsSuccess ? Ok(new { message = "Token revoked." }) : BadRequest(new { error = result.Error });
    }
}
