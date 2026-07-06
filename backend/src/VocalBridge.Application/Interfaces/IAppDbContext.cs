using Microsoft.EntityFrameworkCore;
using VocalBridge.Domain.Entities;

namespace VocalBridge.Application.Interfaces;

/// <summary>
/// Abstraction over EF Core DbContext.
/// Defined in Application so services can query via LINQ
/// without depending on the actual EF Core implementation.
///
/// This replaces the need for generic repositories.
/// EF Core's DbSet IS the repository. This interface IS the unit of work.
/// </summary>
public interface IAppDbContext
{
    DbSet<User> Users { get; }
    DbSet<Video> Videos { get; }
    DbSet<Audio> Audios { get; }
    DbSet<TranslationJob> TranslationJobs { get; }
    DbSet<RefreshToken> RefreshTokens { get; }

    Task<int> SaveChangesAsync(CancellationToken cancellationToken = default);
}
