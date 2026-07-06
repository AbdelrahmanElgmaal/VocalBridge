namespace VocalBridge.Infrastructure.Storage.Settings;

/// <summary>
/// Supabase configuration bound from appsettings.json → "Supabase" section.
/// </summary>
public class SupabaseSettings
{
    public string Url { get; set; } = string.Empty;
    public string ServiceKey { get; set; } = string.Empty;
    public string BucketName { get; set; } = "videos";
}
