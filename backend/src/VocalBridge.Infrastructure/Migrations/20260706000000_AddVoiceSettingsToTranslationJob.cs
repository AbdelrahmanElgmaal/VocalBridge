using Microsoft.EntityFrameworkCore.Migrations;
using Microsoft.EntityFrameworkCore.Infrastructure;
using VocalBridge.Infrastructure.Persistence;

#nullable disable

namespace VocalBridge.Infrastructure.Migrations
{
    [DbContext(typeof(AppDbContext))]
    [Migration("20260706000000_AddVoiceSettingsToTranslationJob")]
    public partial class AddVoiceSettingsToTranslationJob : Migration
    {
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<bool>(
                name: "VoiceCloning",
                table: "TranslationJobs",
                type: "bit",
                nullable: true);

            migrationBuilder.AddColumn<bool>(
                name: "BurnSubtitles",
                table: "TranslationJobs",
                type: "bit",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "VoiceGender",
                table: "TranslationJobs",
                type: "nvarchar(50)",
                maxLength: 50,
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "VoiceAge",
                table: "TranslationJobs",
                type: "nvarchar(50)",
                maxLength: 50,
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "VoicePitch",
                table: "TranslationJobs",
                type: "nvarchar(50)",
                maxLength: 50,
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "VoiceStyle",
                table: "TranslationJobs",
                type: "nvarchar(50)",
                maxLength: 50,
                nullable: true);
        }

        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(name: "VoiceCloning", table: "TranslationJobs");
            migrationBuilder.DropColumn(name: "BurnSubtitles", table: "TranslationJobs");
            migrationBuilder.DropColumn(name: "VoiceGender", table: "TranslationJobs");
            migrationBuilder.DropColumn(name: "VoiceAge", table: "TranslationJobs");
            migrationBuilder.DropColumn(name: "VoicePitch", table: "TranslationJobs");
            migrationBuilder.DropColumn(name: "VoiceStyle", table: "TranslationJobs");
        }
    }
}
