using Microsoft.EntityFrameworkCore;
using VocalBridge.Application.Interfaces;
using VocalBridge.Domain.Entities;

namespace VocalBridge.Infrastructure.Persistence;

/// <summary>
/// EF Core DbContext — the single gateway to SQL Server.
/// Implements IAppDbContext so Application services can query via LINQ
/// without coupling to EF Core directly.
/// </summary>
public class AppDbContext : DbContext, IAppDbContext
{
    public AppDbContext(DbContextOptions<AppDbContext> options) : base(options) { }

    public DbSet<User> Users => Set<User>();
    public DbSet<Video> Videos => Set<Video>();
    public DbSet<Audio> Audios => Set<Audio>();
    public DbSet<TranslationJob> TranslationJobs => Set<TranslationJob>();
    public DbSet<RefreshToken> RefreshTokens => Set<RefreshToken>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        // Apply all IEntityTypeConfiguration<T> classes from this assembly
        modelBuilder.ApplyConfigurationsFromAssembly(typeof(AppDbContext).Assembly);
        base.OnModelCreating(modelBuilder);
    }
}
