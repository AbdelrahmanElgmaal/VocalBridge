import { AlertTriangle, ArrowLeft, RotateCcw } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Button } from "./Button";

interface ErrorCardProps {
  title?: string;
  message: string;
  onRetry?: () => void;
}

export function ErrorCard({ title = "Something went wrong", message, onRetry }: ErrorCardProps) {
  const navigate = useNavigate();

  return (
    <div className="glass rounded-xl border-rose-400/25 p-6">
      <div className="flex gap-4">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-rose-500/12 text-rose-300">
          <AlertTriangle className="h-6 w-6" />
        </div>
        <div>
          <h3 className="text-lg font-semibold text-[var(--text)]">{title}</h3>
          <p className="mt-2 text-sm leading-6 text-[var(--muted)]">{message}</p>
          <div className="mt-5 flex flex-wrap gap-3">
            {onRetry && (
              <Button variant="secondary" onClick={onRetry}>
                <RotateCcw className="h-4 w-4" />
                Retry
              </Button>
            )}
            <Button variant="ghost" onClick={() => navigate("/dashboard")}>
              <ArrowLeft className="h-4 w-4" />
              Return to Dashboard
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
