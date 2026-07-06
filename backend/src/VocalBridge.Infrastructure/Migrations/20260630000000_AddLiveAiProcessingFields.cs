using Microsoft.EntityFrameworkCore.Migrations;
using Microsoft.EntityFrameworkCore.Infrastructure;
using VocalBridge.Infrastructure.Persistence;

#nullable disable

namespace VocalBridge.Infrastructure.Migrations
{
    [DbContext(typeof(AppDbContext))]
    [Migration("20260630000000_AddLiveAiProcessingFields")]
    public partial class AddLiveAiProcessingFields : Migration
    {
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<string>(
                name: "CurrentStage",
                table: "TranslationJobs",
                type: "nvarchar(100)",
                maxLength: 100,
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "Transcript",
                table: "TranslationJobs",
                type: "nvarchar(max)",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "TranslatedText",
                table: "TranslationJobs",
                type: "nvarchar(max)",
                nullable: true);
        }

        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(
                name: "CurrentStage",
                table: "TranslationJobs");

            migrationBuilder.DropColumn(
                name: "Transcript",
                table: "TranslationJobs");

            migrationBuilder.DropColumn(
                name: "TranslatedText",
                table: "TranslationJobs");
        }
    }
}
