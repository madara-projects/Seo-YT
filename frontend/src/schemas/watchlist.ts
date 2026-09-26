import { z } from "zod";
import type { LabelledOption } from "@/lib/labels";

/**
 * Adding to the watchlist looks the item up on YouTube, which spends quota, so
 * an identifier the lookup cannot resolve is caught here instead.
 */

const CHANNEL_ID = /^UC[A-Za-z0-9_-]{22}$/;

/**
 * The channel ID from an ID or a `/channel/UC…` link. The backend looks
 * channels up by ID only, so handles (`@name`) and custom URLs resolve to null.
 */
export function extractChannelId(value: string): string | null {
  const candidate = value.trim();
  if (CHANNEL_ID.test(candidate)) return candidate;
  const match = candidate.match(/\/channel\/(UC[A-Za-z0-9_-]{22})(?:[/?#]|$)/);
  return match?.[1] ?? null;
}

const VIDEO_ID = /^[A-Za-z0-9_-]{11}$/;
const YOUTUBE_HOSTS = new Set(["youtube.com", "m.youtube.com", "music.youtube.com", "youtube-nocookie.com"]);

/**
 * Mirrors `_extract_youtube_video_id` in the backend routes: a bare
 * 11-character ID, youtu.be/<id>, or a YouTube host with `?v=<id>` or
 * /shorts|embed|live|v/<id>. Any other host is refused, and a longer ID is
 * refused rather than cut to 11 characters.
 */
export function extractVideoId(value: string): string | null {
  const candidate = value.trim();
  if (VIDEO_ID.test(candidate)) return candidate;
  let url: URL;
  try {
    url = new URL(candidate.includes("://") ? candidate : `https://${candidate}`);
  } catch {
    return null;
  }
  const host = url.hostname.toLowerCase().replace(/^www\./, "");
  if (host === "youtu.be") return url.pathname.match(/^\/([A-Za-z0-9_-]{11})\/?$/)?.[1] ?? null;
  if (!YOUTUBE_HOSTS.has(host)) return null;
  // Like the server's `parse_qs`, the first non-empty `v` counts.
  const v = url.searchParams.getAll("v").find(Boolean) ?? "";
  if (VIDEO_ID.test(v)) return v;
  return url.pathname.match(/^\/(?:shorts|embed|live|v)\/([A-Za-z0-9_-]{11})\/?$/)?.[1] ?? null;
}

const notes = z.string().trim().max(2000, "Notes are limited to 2,000 characters.");

export const addChannelSchema = z.object({
  channel: z
    .string()
    .trim()
    .min(1, "Enter a channel ID.")
    .max(100, "That is longer than a channel ID or link.")
    .refine((value) => !value.startsWith("@") && !value.includes("/@"), {
      message: "Handles can't be looked up. Use the channel ID that starts with UC (Share channel → Copy channel ID).",
    })
    .refine((value) => value.startsWith("@") || value.includes("/@") || extractChannelId(value) !== null, {
      message: "Enter a channel ID that starts with UC, or a youtube.com/channel/UC… link.",
    }),
  notes,
});

export const addVideoSchema = z.object({
  video: z
    .string()
    .trim()
    .min(1, "Enter a video ID or link.")
    .max(200, "That is longer than a YouTube link.")
    .refine((value) => extractVideoId(value) !== null, {
      message: "Enter an 11-character video ID or a YouTube video link.",
    }),
  notes,
});

export type AddChannelValues = z.infer<typeof addChannelSchema>;
export type AddVideoValues = z.infer<typeof addVideoSchema>;

export const WATCH_STATE_FILTERS: LabelledOption[] = [
  { value: "active", label: "Active" },
  { value: "archived", label: "Archived" },
  { value: "", label: "All" },
];
