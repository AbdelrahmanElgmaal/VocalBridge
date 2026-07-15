using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace VocalBridge.Infrastructure.AI.Migrations
{
    /// <inheritdoc />
    public partial class AddEnableLipsyncToTranslationJob : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<bool>(
                name: "EnableLipsync",
                table: "TranslationJobs",
                type: "bit",
                nullable: false,
                defaultValue: false);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(
                name: "EnableLipsync",
                table: "TranslationJobs");
        }
    }
}
