import { useState } from "react";
import { PlayCircle } from "lucide-react";
import { cn } from "@/lib/utils";

const VIDEO_ID = /^[A-Za-z0-9_-]{6,20}$/;

/**
 * A public YouTube thumbnail, falling back to a branded placeholder when the
 * id is missing or the image cannot load (offline, blocked, or removed).
 */
export function VideoThumb({
  videoId,
  title,
  className,
}: {
  videoId?: string | null;
  title?: string;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);
  const usable = Boolean(videoId && VIDEO_ID.test(videoId)) && !failed;

  return (
    <div
      className={cn(
        "relative aspect-video shrink-0 overflow-hidden rounded-lg bg-muted ring-1 ring-inset ring-border",
        className,
      )}
    >
      {usable ? (
        <img
          src={`https://i.ytimg.com/vi/${videoId}/mqdefault.jpg`}
          alt={title ? `Thumbnail: ${title}` : ""}
          loading="lazy"
          decoding="async"
          referrerPolicy="no-referrer"
          onError={() => setFailed(true)}
          className="size-full object-cover"
        />
      ) : (
        <div className="grid size-full place-items-center bg-brand-gradient text-white/90" aria-hidden="true">
          <PlayCircle className="size-5" />
        </div>
      )}
    </div>
  );
}
