import { cn } from "@/lib/utils";

/**
 * A stand-in thumbnail that shows the suggested on-image text at thumbnail
 * scale, so a creator can judge whether it reads at a glance. It is a mock,
 * not a generated image, and is labelled as such where it is used.
 */
export function ThumbnailMock({
  text,
  duration,
  className,
}: {
  text: string;
  duration?: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "@container relative aspect-video overflow-hidden rounded-xl bg-[oklch(0.2_0.05_290)] shadow-card",
        className,
      )}
      aria-hidden="true"
    >
      <div className="absolute inset-0 bg-brand-gradient opacity-90" />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_25%_15%,oklch(1_0_0/0.35),transparent_55%)]" />
      <div className="absolute inset-0 bg-[radial-gradient(oklch(1_0_0/0.14)_1px,transparent_1px)] [background-size:14px_14px]" />
      <div className="absolute inset-x-0 bottom-0 h-3/4 bg-linear-to-t from-black/60 via-black/20 to-transparent" />
      <p className="absolute inset-x-[5%] bottom-[8%] line-clamp-3 font-display text-[clamp(13px,9cqw,40px)] font-extrabold uppercase leading-[0.95] tracking-tight text-white drop-shadow-[0_2px_10px_rgba(0,0,0,0.45)]">
        {text || "No thumbnail text"}
      </p>
      {duration ? (
        <span className="numeric absolute bottom-[6%] right-[3%] rounded-md bg-black/80 px-1.5 py-0.5 text-[10px] font-medium text-white">
          {duration}
        </span>
      ) : null}
    </div>
  );
}
