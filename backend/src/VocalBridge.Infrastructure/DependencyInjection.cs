using System.Text;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.IdentityModel.Tokens;
using VocalBridge.Application.Interfaces;
using VocalBridge.Infrastructure.AI;
using VocalBridge.Infrastructure.AI.Settings;
using VocalBridge.Infrastructure.BackgroundJobs;
using VocalBridge.Infrastructure.Identity;
using VocalBridge.Infrastructure.Identity.Settings;
using VocalBridge.Infrastructure.Persistence;
using VocalBridge.Infrastructure.Storage;
using VocalBridge.Infrastructure.Storage.Settings;

namespace VocalBridge.Infrastructure;

/// <summary>
/// Registers all Infrastructure services into the DI container.
/// Called from Program.cs via: builder.Services.AddInfrastructure(config);
/// </summary>
public static class DependencyInjection
{
    public static IServiceCollection AddInfrastructure(
        this IServiceCollection services, IConfiguration configuration)
    {
        // ── Database ──
        services.AddDbContext<AppDbContext>(options =>
            options.UseSqlServer(
                configuration.GetConnectionString("Default"),
                b => b.MigrationsAssembly(typeof(AppDbContext).Assembly.FullName)));

        services.AddScoped<IAppDbContext>(sp =>
            sp.GetRequiredService<AppDbContext>());

        // ── Authentication (JWT) ──
        var jwtSettings = configuration.GetSection("Jwt").Get<JwtSettings>()!;
        services.Configure<JwtSettings>(configuration.GetSection("Jwt"));
        services.AddScoped<JwtProvider>();
        services.AddScoped<IAuthService, AuthService>();

        services.AddAuthentication(options =>
        {
            options.DefaultAuthenticateScheme = JwtBearerDefaults.AuthenticationScheme;
            options.DefaultChallengeScheme = JwtBearerDefaults.AuthenticationScheme;
        })
        .AddJwtBearer(options =>
        {
            options.TokenValidationParameters = new TokenValidationParameters
            {
                ValidateIssuer = true,
                ValidIssuer = jwtSettings.Issuer,
                ValidateAudience = true,
                ValidAudience = jwtSettings.Audience,
                ValidateIssuerSigningKey = true,
                IssuerSigningKey = new SymmetricSecurityKey(
                    Encoding.UTF8.GetBytes(jwtSettings.SecretKey)),
                ValidateLifetime = true,
                ClockSkew = TimeSpan.Zero,
            };
        });

        services.AddAuthorization();

        // ── Supabase Storage ──
        services.Configure<SupabaseSettings>(configuration.GetSection("Supabase"));
        services.AddScoped<IStorageService, SupabaseStorageService>();

        // ── AI Service ──
        services.Configure<AiServiceSettings>(configuration.GetSection("AiService"));
        services.AddHttpClient<IAiService, AiDubbingService>();
        services.AddSingleton<IWebhookSettings, WebhookSettingsAdapter>();

        // ── Background Jobs ──
        services.AddHostedService<AiJobPollingWorker>();

        return services;
    }
}
