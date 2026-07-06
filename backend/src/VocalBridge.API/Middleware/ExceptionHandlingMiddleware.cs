using System.Net;
using System.Text.Json;
using FluentValidation;

namespace VocalBridge.API.Middleware;

/// <summary>
/// Global exception handler — catches all unhandled exceptions and
/// returns structured JSON error responses.
///
/// Controllers never need try/catch. This middleware handles everything:
///   - ValidationException   → 400
///   - UnauthorizedAccess    → 401
///   - KeyNotFoundException  → 404
///   - Everything else       → 500
/// </summary>
public class ExceptionHandlingMiddleware
{
    private readonly RequestDelegate _next;
    private readonly ILogger<ExceptionHandlingMiddleware> _logger;

    public ExceptionHandlingMiddleware(RequestDelegate next, ILogger<ExceptionHandlingMiddleware> logger)
    {
        _next = next;
        _logger = logger;
    }

    public async Task InvokeAsync(HttpContext context)
    {
        try
        {
            await _next(context);
        }
        catch (ValidationException ex)
        {
            _logger.LogWarning("Validation failed: {Errors}", ex.Message);
            await WriteResponse(context, HttpStatusCode.BadRequest, new
            {
                error = "Validation failed.",
                details = ex.Errors.Select(e => new { e.PropertyName, e.ErrorMessage })
            });
        }
        catch (UnauthorizedAccessException ex)
        {
            _logger.LogWarning("Unauthorized: {Message}", ex.Message);
            await WriteResponse(context, HttpStatusCode.Unauthorized, new
            {
                error = ex.Message ?? "Unauthorized."
            });
        }
        catch (KeyNotFoundException ex)
        {
            await WriteResponse(context, HttpStatusCode.NotFound, new
            {
                error = ex.Message ?? "Resource not found."
            });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Unhandled exception");
            await WriteResponse(context, HttpStatusCode.InternalServerError, new
            {
                error = "An unexpected error occurred. Please try again later."
            });
        }
    }

    private static async Task WriteResponse(HttpContext context, HttpStatusCode statusCode, object body)
    {
        context.Response.StatusCode = (int)statusCode;
        context.Response.ContentType = "application/json";
        await context.Response.WriteAsync(JsonSerializer.Serialize(body, new JsonSerializerOptions
        {
            PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        }));
    }
}
