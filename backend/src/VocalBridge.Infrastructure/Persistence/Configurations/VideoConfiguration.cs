using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using VocalBridge.Domain.Entities;
using VocalBridge.Domain.Enums;

namespace VocalBridge.Infrastructure.Persistence.Configurations;

public class VideoConfiguration : IEntityTypeConfiguration<Video>
{
    public void Configure(EntityTypeBuilder<Video> builder)
    {
        builder.HasKey(v => v.Id);

        builder.Property(v => v.FileName)
            .IsRequired()
            .HasMaxLength(256);

        builder.Property(v => v.SourceType)
            .IsRequired()
            .HasConversion<string>()
            .HasMaxLength(20);

        builder.Property(v => v.StoragePath)
            .HasMaxLength(500);

        builder.Property(v => v.OriginalVideoUrl)
            .HasMaxLength(2000);

        builder.HasMany(v => v.TranslationJobs)
            .WithOne(j => j.Video)
            .HasForeignKey(j => j.VideoId)
            .OnDelete(DeleteBehavior.Cascade);

        // CHECK constraint: exactly one of StoragePath or OriginalVideoUrl must be set
        builder.ToTable(t => t.HasCheckConstraint(
            "CK_Video_Source",
            "(([SourceType] = 'Uploaded' AND [StoragePath] IS NOT NULL AND [OriginalVideoUrl] IS NULL) OR " +
            "([SourceType] = 'ExternalUrl' AND [OriginalVideoUrl] IS NOT NULL AND [StoragePath] IS NULL))"));
    }
}
