import { Modal } from "../ui/Modal";
import { MediaPreview } from "../ui/MediaPreview";

interface VideoPlayerModalProps {
  open: boolean;
  title: string;
  url?: string | null;
  onClose: () => void;
}

export function VideoPlayerModal({ open, title, url, onClose }: VideoPlayerModalProps) {
  return (
    <Modal open={open} title={title} onClose={onClose}>
      {url ? (
        <MediaPreview url={url} title={title} autoPlay />
      ) : (
        <div className="flex aspect-video items-center justify-center rounded-lg bg-black/70 text-sm text-slate-400">
          Signed URL is not available for this item.
        </div>
      )}
    </Modal>
  );
}
