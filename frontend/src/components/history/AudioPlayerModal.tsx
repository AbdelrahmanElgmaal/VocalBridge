import { Modal } from "../ui/Modal";

interface AudioPlayerModalProps {
  open: boolean;
  title: string;
  url?: string | null;
  onClose: () => void;
}

export function AudioPlayerModal({ open, title, url, onClose }: AudioPlayerModalProps) {
  return (
    <Modal open={open} title={title} onClose={onClose}>
      {url ? (
        <div className="flex flex-col items-center justify-center p-6 bg-black/40 rounded-lg">
          <div className="w-24 h-24 rounded-full bg-electric/10 flex items-center justify-center mb-6">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-10 w-10 text-electric" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 18V5l12-2v13"></path>
              <circle cx="6" cy="18" r="3"></circle>
              <circle cx="18" cy="16" r="3"></circle>
            </svg>
          </div>
          <audio src={url} controls autoPlay className="w-full max-w-md outline-none" />
        </div>
      ) : (
        <div className="flex h-40 items-center justify-center rounded-lg bg-black/70 text-sm text-slate-400">
          Audio URL is not available for this item.
        </div>
      )}
    </Modal>
  );
}
