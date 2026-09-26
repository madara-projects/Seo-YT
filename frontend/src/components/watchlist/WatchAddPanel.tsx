import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Binoculars, Loader2, Plus, Tv, Youtube } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { FormField } from "@/components/common/FormField";
import { Inset, Panel } from "@/components/common/Panel";
import { ErrorState } from "@/components/common/States";
import { apiErrorMessage, apiRequestId } from "@/api/client";
import { useAddWatchChannel, useAddWatchVideo } from "@/hooks/useWatchlist";
import {
  addChannelSchema,
  addVideoSchema,
  extractChannelId,
  extractVideoId,
  type AddChannelValues,
  type AddVideoValues,
} from "@/schemas/watchlist";
import type { WatchKind } from "@/api/watchlistTypes";

function ChannelForm({ onAdded }: { onAdded: (id: number) => void }) {
  const form = useForm<AddChannelValues>({
    resolver: zodResolver(addChannelSchema),
    defaultValues: { channel: "", notes: "" },
    mode: "onSubmit",
  });
  const add = useAddWatchChannel();
  const errors = form.formState.errors;

  // A failure is shown under the form with its request ID.
  const submit = form.handleSubmit((values) => {
    // Per-call callbacks don't run once the form has unmounted, so an add that
    // finishes after the creator has left never pulls them back to this page.
    add.mutate(
      { channel_id: extractChannelId(values.channel) ?? "", notes: values.notes },
      {
        onSuccess: (data) => {
          toast.success(`Now watching ${data.channel?.title || "the channel"}.`);
          form.reset();
          add.reset();
          if (data.channel?.id) onAdded(data.channel.id);
        },
      },
    );
  });

  return (
    <Inset className="flex flex-col gap-4 p-4">
      <p className="inline-flex items-center gap-2 text-sm font-semibold text-foreground">
        <Tv className="size-4 text-muted-foreground" aria-hidden="true" />A channel
      </p>
      <form onSubmit={submit} noValidate className="flex flex-1 flex-col gap-3">
        <FormField
          id="watch-channel"
          label="Channel ID or link"
          error={errors.channel?.message}
          hint="The ID starts with UC: Share channel → Copy channel ID."
        >
          <Input
            id="watch-channel"
            placeholder="UC… or youtube.com/channel/UC…"
            maxLength={100}
            autoComplete="off"
            aria-invalid={Boolean(errors.channel)}
            {...form.register("channel")}
          />
        </FormField>
        <FormField id="watch-channel-notes" label="Notes" optional error={errors.notes?.message}>
          <Input id="watch-channel-notes" maxLength={2000} autoComplete="off" {...form.register("notes")} />
        </FormField>
        {add.isError ? (
          <ErrorState message={apiErrorMessage(add.error, "Could not add this channel.")} requestId={apiRequestId(add.error)} />
        ) : null}
        <Button type="submit" variant="outline" disabled={add.isPending} className="mt-auto">
          {add.isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Plus aria-hidden="true" />}
          {add.isPending ? "Looking it up…" : "Add channel"}
        </Button>
      </form>
    </Inset>
  );
}

function VideoForm({ onAdded }: { onAdded: (id: number) => void }) {
  const form = useForm<AddVideoValues>({
    resolver: zodResolver(addVideoSchema),
    defaultValues: { video: "", notes: "" },
    mode: "onSubmit",
  });
  const add = useAddWatchVideo();
  const errors = form.formState.errors;

  // A failure is shown under the form with its request ID.
  const submit = form.handleSubmit((values) => {
    // Per-call callbacks don't run once the form has unmounted, so an add that
    // finishes after the creator has left never pulls them back to this page.
    add.mutate(
      { video_id: extractVideoId(values.video) ?? "", notes: values.notes },
      {
        onSuccess: (data) => {
          toast.success("Video added. Refresh it to capture its first snapshot.");
          form.reset();
          add.reset();
          if (data.video?.id) onAdded(data.video.id);
        },
      },
    );
  });

  return (
    <Inset className="flex flex-col gap-4 p-4">
      <p className="inline-flex items-center gap-2 text-sm font-semibold text-foreground">
        <Youtube className="size-4 text-muted-foreground" aria-hidden="true" />A video
      </p>
      <form onSubmit={submit} noValidate className="flex flex-1 flex-col gap-3">
        <FormField
          id="watch-video"
          label="Video ID or link"
          error={errors.video?.message}
          hint="A youtube.com, youtu.be or Shorts link works."
        >
          <Input
            id="watch-video"
            placeholder="https://youtu.be/…"
            maxLength={200}
            autoComplete="off"
            aria-invalid={Boolean(errors.video)}
            {...form.register("video")}
          />
        </FormField>
        <FormField id="watch-video-notes" label="Notes" optional error={errors.notes?.message}>
          <Input id="watch-video-notes" maxLength={2000} autoComplete="off" {...form.register("notes")} />
        </FormField>
        {add.isError ? (
          <ErrorState message={apiErrorMessage(add.error, "Could not add this video.")} requestId={apiRequestId(add.error)} />
        ) : null}
        <Button type="submit" variant="outline" disabled={add.isPending} className="mt-auto">
          {add.isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Plus aria-hidden="true" />}
          {add.isPending ? "Looking it up…" : "Add video"}
        </Button>
      </form>
    </Inset>
  );
}

export function WatchAddPanel({ onAdded }: { onAdded: (kind: WatchKind, id: number) => void }) {
  return (
    <Panel
      icon={Binoculars}
      title="Watch something new"
      description="Adding looks it up on YouTube for one quota unit. Refresh it later to capture dated numbers."
      aside={<EvidenceChip tone="info">Public data, read-only</EvidenceChip>}
    >
      <div className="grid gap-4 md:grid-cols-2">
        <ChannelForm onAdded={(id) => onAdded("channel", id)} />
        <VideoForm onAdded={(id) => onAdded("video", id)} />
      </div>
    </Panel>
  );
}
