using VocalBridge.API.Middleware;
using VocalBridge.API.Services;
using VocalBridge.Application;
using VocalBridge.Application.Interfaces;
using VocalBridge.Infrastructure;

var builder = WebApplication.CreateBuilder(args);

// ── Layer Registration ──────────────────────────────────────
builder.Services.AddApplication();
builder.Services.AddInfrastructure(builder.Configuration);

// ── API Services ────────────────────────────────────────────
builder.Services.AddHttpContextAccessor();
builder.Services.AddScoped<ICurrentUserService, CurrentUserService>();
builder.Services.AddControllers();

// ── Swagger ─────────────────────────────────────────────────
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen(options =>
{
    options.SwaggerDoc("v1", new()
    {
        Title = "Vocal Bridge API",
        Version = "v1",
        Description = "AI-powered English → Arabic video dubbing platform.\n\n" +
                      "## Flow\n" +
                      "1. Register / Login → get JWT\n" +
                      "2. Upload a video OR submit a public URL\n" +
                      "3. Create a translation job (always EN → AR)\n" +
                      "4. Poll status or wait for webhook\n" +
                      "5. Retrieve the dubbed Arabic video via signed URL"
    });

    // JWT Bearer token input in Swagger UI
    options.AddSecurityDefinition("Bearer", new()
    {
        Name = "Authorization",
        Type = Microsoft.OpenApi.Models.SecuritySchemeType.Http,
        Scheme = "bearer",
        BearerFormat = "JWT",
        Description = "Paste your JWT access token from /api/auth/login"
    });

    options.AddSecurityRequirement(new()
    {
        {
            new Microsoft.OpenApi.Models.OpenApiSecurityScheme
            {
                Reference = new() { Type = Microsoft.OpenApi.Models.ReferenceType.SecurityScheme, Id = "Bearer" }
            },
            Array.Empty<string>()
        }
    });
});

// ── CORS ────────────────────────────────────────────────────
// builder.Services.AddCors(options =>
// {
//     options.AddPolicy("AllowFrontend", policy =>
//     {
//         policy
//             .WithOrigins(
//                 builder.Configuration.GetSection("Cors:AllowedOrigins").Get<string[]>()
//                 ?? new[] { "http://localhost:3000" })
//             .AllowAnyMethod()
//             .AllowAnyHeader()
//             .AllowCredentials();
//     });
// });

builder.Services.AddCors(options =>
{
    options.AddPolicy("AllowFrontend", policy =>
    {
        policy
            .AllowAnyOrigin() // يقبل من أي مكان ومن أي بورت
            .AllowAnyMethod()
            .AllowAnyHeader();
        // شيلنا AllowCredentials مؤقتاً لأنها تمنع استخدام AllowAnyOrigin
    });
});


var app = builder.Build();

// ── Middleware Pipeline ──────────────────────────────────────
app.UseMiddleware<ExceptionHandlingMiddleware>();

if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

app.UseHttpsRedirection();
app.UseCors("AllowFrontend");
app.UseAuthentication();
app.UseAuthorization();
app.MapControllers();

app.Run();
