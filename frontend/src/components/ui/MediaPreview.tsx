import { PlayCircle } from "lucide-react";
import { getYouTubeEmbedUrl, isDirectVideoUrl } from "../../lib/media";

interface MediaPreviewProps {
  url?: string | null;
  title?: string;
  className?: string;
  autoPlay?: boolean;
}

export function MediaPreview({ url, title = "Video preview", className = "", autoPlay = false }: MediaPreviewProps) {
  const youtubeEmbed = url ? getYouTubeEmbedUrl(url) : "";
  const directVideo = url ? isDirectVideoUrl(url) || url.startsWith("blob:") : false;

  if (youtubeEmbed) {
    return (
      <iframe
        title={title}
        src={youtubeEmbed}
        className={`aspect-video w-full rounded-xl bg-black ${className}`}
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
        allowFullScreen
      />
    );
  }

  if (url && directVideo) {
    return <video src={url} controls autoPlay={autoPlay} className={`aspect-video w-full rounded-xl bg-black object-contain ${className}`} />;
  }

  return (
    <div className={`flex aspect-video w-full items-center justify-center rounded-xl bg-black/60 ${className}`}>
      <div className="text-center">
        <PlayCircle className="mx-auto h-12 w-12 text-white/40" />
        <p className="mt-3 max-w-sm text-sm leading-6 text-white/55">Preview unavailable for this source.</p>
      </div>
    </div>
  );
}
