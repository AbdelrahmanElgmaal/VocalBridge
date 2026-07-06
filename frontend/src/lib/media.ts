export function getYouTubeEmbedUrl(url: string) {
  try {
    const parsed = new URL(url);
    const host = parsed.hostname.replace(/^www\./, "");
    if (host === "youtu.be") {
      const id = parsed.pathname.split("/").filter(Boolean)[0];
      return id ? `https://www.youtube.com/embed/${id}` : "";
    }
    if (host === "youtube.com" || host === "m.youtube.com") {
      const parts = parsed.pathname.split("/").filter(Boolean);
      if (parts[0] === "embed" && parts[1]) return `https://www.youtube.com/embed/${parts[1]}`;
      if (parts[0] === "shorts" && parts[1]) return `https://www.youtube.com/embed/${parts[1]}`;
      if (parts[0] === "live" && parts[1]) return `https://www.youtube.com/embed/${parts[1]}`;
      const id = parsed.searchParams.get("v");
      return id ? `https://www.youtube.com/embed/${id}` : "";
    }
  } catch {
    return "";
  }
  return "";
}

export function isDirectVideoUrl(url: string) {
  return /\.(mp4|webm|mov|m4v|ogg|avi|mkv)(\?.*)?$/i.test(url);
}

export function canPreviewUrl(url: string) {
  return Boolean(getYouTubeEmbedUrl(url) || isDirectVideoUrl(url));
}

export async function downloadFile(url: string, filename: string) {
  const response = await fetch(url, { mode: "cors" });
  if (!response.ok) throw new Error("The video file could not be downloaded.");

  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  const safeFilename = /\.[a-z0-9]{2,5}$/i.test(filename) ? filename : `${filename}.mp4`;
  anchor.href = objectUrl;
  anchor.download = safeFilename || "vocal-bridge-video.mp4";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
}
