using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace VocalBridge.Infrastructure.Migrations
{
    /// <inheritdoc />
    public partial class AddVoiceDubbingSupport : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AlterColumn<Guid>(
                name: "VideoId",
                table: "TranslationJobs",
                type: "uniqueidentifier",
                nullable: true,
                oldClrType: typeof(Guid),
                oldType: "uniqueidentifier");

            migrationBuilder.AddColumn<Guid>(
                name: "AudioId",
                table: "TranslationJobs",
                type: "uniqueidentifier",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "InputType",
                table: "TranslationJobs",
                type: "nvarchar(20)",
                maxLength: 20,
                nullable: false,
                defaultValue: "");

            migrationBuilder.AddColumn<string>(
                name: "OutputType",
                table: "TranslationJobs",
                type: "nvarchar(20)",
                maxLength: 20,
                nullable: false,
                defaultValue: "");

            migrationBuilder.AddColumn<string>(
                name: "TranslatedAudioPath",
                table: "TranslationJobs",
                type: "nvarchar(500)",
                maxLength: 500,
                nullable: true);

            migrationBuilder.CreateTable(
                name: "Audios",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uniqueidentifier", nullable: false),
                    UserId = table.Column<Guid>(type: "uniqueidentifier", nullable: false),
                    FileName = table.Column<string>(type: "nvarchar(255)", maxLength: 255, nullable: false),
                    FileSize = table.Column<long>(type: "bigint", nullable: false),
                    DurationSeconds = table.Column<double>(type: "float", nullable: false),
                    StoragePath = table.Column<string>(type: "nvarchar(500)", maxLength: 500, nullable: true),
                    OriginalAudioUrl = table.Column<string>(type: "nvarchar(1000)", maxLength: 1000, nullable: true),
                    CreatedAt = table.Column<DateTime>(type: "datetime2", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Audios", x => x.Id);
                    table.ForeignKey(
                        name: "FK_Audios_Users_UserId",
                        column: x => x.UserId,
                        principalTable: "Users",
                        principalColumn: "Id");
                });

            migrationBuilder.CreateIndex(
                name: "IX_TranslationJobs_AudioId",
                table: "TranslationJobs",
                column: "AudioId");

            migrationBuilder.CreateIndex(
                name: "IX_Audios_UserId",
                table: "Audios",
                column: "UserId");

            migrationBuilder.AddForeignKey(
                name: "FK_TranslationJobs_Audios_AudioId",
                table: "TranslationJobs",
                column: "AudioId",
                principalTable: "Audios",
                principalColumn: "Id");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropForeignKey(
                name: "FK_TranslationJobs_Audios_AudioId",
                table: "TranslationJobs");

            migrationBuilder.DropTable(
                name: "Audios");

            migrationBuilder.DropIndex(
                name: "IX_TranslationJobs_AudioId",
                table: "TranslationJobs");

            migrationBuilder.DropColumn(
                name: "AudioId",
                table: "TranslationJobs");

            migrationBuilder.DropColumn(
                name: "InputType",
                table: "TranslationJobs");

            migrationBuilder.DropColumn(
                name: "OutputType",
                table: "TranslationJobs");

            migrationBuilder.DropColumn(
                name: "TranslatedAudioPath",
                table: "TranslationJobs");

            migrationBuilder.AlterColumn<Guid>(
                name: "VideoId",
                table: "TranslationJobs",
                type: "uniqueidentifier",
                nullable: false,
                defaultValue: new Guid("00000000-0000-0000-0000-000000000000"),
                oldClrType: typeof(Guid),
                oldType: "uniqueidentifier",
                oldNullable: true);
        }
    }
}
