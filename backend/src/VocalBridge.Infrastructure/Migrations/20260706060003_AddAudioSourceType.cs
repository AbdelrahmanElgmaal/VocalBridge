using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace VocalBridge.Infrastructure.Migrations
{
    /// <inheritdoc />
    public partial class AddAudioSourceType : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<int>(
                name: "SourceType",
                table: "Audios",
                type: "int",
                nullable: false,
                defaultValue: 0);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(
                name: "SourceType",
                table: "Audios");
        }
    }
}
