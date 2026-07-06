using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using VocalBridge.Domain.Entities;

namespace VocalBridge.Infrastructure.Persistence.Configurations;

public class AudioConfiguration : IEntityTypeConfiguration<Audio>
{
    public void Configure(EntityTypeBuilder<Audio> builder)
    {
        builder.HasKey(a => a.Id);

        builder.Property(a => a.FileName)
            .IsRequired()
            .HasMaxLength(255);

        builder.Property(a => a.StoragePath)
            .HasMaxLength(500);

        builder.Property(a => a.OriginalAudioUrl)
            .HasMaxLength(1000);

        builder.HasOne(a => a.User)
            .WithMany()
            .HasForeignKey(a => a.UserId)
            .OnDelete(DeleteBehavior.NoAction);
    }
}
