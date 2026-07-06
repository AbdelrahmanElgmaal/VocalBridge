using FluentValidation;
using Microsoft.Extensions.DependencyInjection;
using VocalBridge.Application.Services;

namespace VocalBridge.Application;

/// <summary>
/// Registers all Application layer services into the DI container.
/// Called from Program.cs via: builder.Services.AddApplication();
/// </summary>
public static class DependencyInjection
{
    public static IServiceCollection AddApplication(this IServiceCollection services)
    {
        var assembly = typeof(DependencyInjection).Assembly;

        // AutoMapper — scans this assembly for Profile classes
        services.AddAutoMapper(assembly);

        // FluentValidation — scans this assembly for AbstractValidator<T> classes
        services.AddValidatorsFromAssembly(assembly);

        // Business Services
        services.AddScoped<VideoService>();
        services.AddScoped<AudioService>();
        services.AddScoped<TranslationService>();

        return services;
    }
}
