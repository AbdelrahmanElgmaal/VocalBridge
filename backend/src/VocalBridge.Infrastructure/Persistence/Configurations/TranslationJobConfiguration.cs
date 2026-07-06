using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using VocalBridge.Domain.Entities;
using VocalBridge.Domain.Enums;

namespace VocalBridge.Infrastructure.Persistence.Configurations;

public class TranslationJobConfiguration : IEntityTypeConfiguration<TranslationJob>
{
    public void Configure(EntityTypeBuilder<TranslationJob> builder)
    {
        builder.HasKey(j => j.Id);

        builder.Property(j => j.AiJobId)
            .HasMaxLength(100);

        builder.HasIndex(j => j.AiJobId);

        builder.Property(j => j.Status)
            .IsRequired()
            .HasConversion<string>()
            .HasMaxLength(20);

        builder.Property(j => j.TranslatedVideoPath)
            .HasMaxLength(500);

        builder.Property(j => j.TranslatedAudioPath)
            .HasMaxLength(500);

        builder.Property(j => j.InputType)
            .IsRequired()
            .HasConversion<string>()
            .HasMaxLength(20);

        builder.Property(j => j.OutputType)
            .IsRequired()
            .HasConversion<string>()
            .HasMaxLength(20);

        builder.Property(j => j.ErrorMessage)
            .HasMaxLength(2000);

        builder.Property(j => j.CurrentStage)
            .HasMaxLength(100);

        builder.Property(j => j.Transcript)
            .HasColumnType("nvarchar(max)");

        builder.Property(j => j.TranslatedText)
            .HasColumnType("nvarchar(max)");

        builder.Property(j => j.VoiceGender).HasMaxLength(50);
        builder.Property(j => j.VoiceAge).HasMaxLength(50);
        builder.Property(j => j.VoicePitch).HasMaxLength(50);
        builder.Property(j => j.VoiceStyle).HasMaxLength(50);

        // FK to User (NoAction to avoid cascade cycles)
        builder.HasOne(j => j.User)
            .WithMany()
            .HasForeignKey(j => j.UserId)
            .OnDelete(DeleteBehavior.NoAction);

        // Optional FK to Audio
        builder.HasOne(j => j.Audio)
            .WithMany()
            .HasForeignKey(j => j.AudioId)
            .OnDelete(DeleteBehavior.NoAction);
    }
}
