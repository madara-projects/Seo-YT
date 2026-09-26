import { useState } from "react";
import { PlayCircle } from "lucide-react";
import { cn } from "@/lib/utils";

const VIDEO_ID = /^[A-Za-z0-9_-]{6,20}$/;

/**
 * A public YouTube thumbnail, falling back to a branded placeholder when the
 * id is missing or the image cannot load (offline, blocked, or removed).
 *
 * Decorative: every use prints the video's title beside it, so alt text
 * would only make a screen reader say the title twice.
 */
export function VideoThumb({
  videoId,
  className,
}: {
  videoId?: string | null;
  className?: string;
}) {
  // Remembers which video failed, so an inspector reused for the next video
  // tries that video's image instead of keeping the placeholder.
  const [failedId, setFailedId] = useState<string | null>(null);
  const usable = Boolean(videoId && VIDEO_ID.test(videoId)) && failedId !== videoId;

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
          alt=""
          loading="lazy"
          decoding="async"
          referrerPolicy="no-referrer"
          onError={() => setFailedId(videoId ?? null)}
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
