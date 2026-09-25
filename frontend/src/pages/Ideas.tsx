import { useEffect, useMemo, useState } from "react";
import { Lightbulb, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EvidenceChip } from "@/components/common/EvidenceChip";
import { PageHeader } from "@/components/common/PageHeader";
import { IdeaDetail } from "@/components/ideas/IdeaDetail";
import { IdeaFormSheet } from "@/components/ideas/IdeaFormSheet";
import { IdeaList } from "@/components/ideas/IdeaList";
import { IDEAS_PAGE_SIZE, useIdea, useIdeas } from "@/hooks/useIdeas";
import { useSelectedId } from "@/hooks/useSelection";
import { asArray } from "@/lib/utils";
import type { IdeaSummary } from "@/api/ideaTypes";

/**
 * The idea backlog: save original topics, research them with approved YouTube
 * data, check demand, and carry one idea at a time into a package. The open
 * idea lives in the URL (`?idea=`), so it can be linked to.
 */
export default function IdeasPage() {
  const { selectedId, select, detailRef } = useSelectedId("idea");
  const [status, setStatus] = useState("");
  const [offset, setOffset] = useState(0);
  const [formOpen, setFormOpen] = useState(false);

  const list = useIdeas(status, offset);
  const detail = useIdea(selectedId);
  const ideas = useMemo(() => asArray<IdeaSummary>(list.data?.ideas), [list.data]);
  const total = typeof list.data?.total === "number" ? list.data.total : ideas.length;

  // A status change can empty the page being viewed; step back to the last one.
  useEffect(() => {
    if (!list.isPlaceholderData && list.isSuccess && !ideas.length && offset > 0) {
      setOffset(Math.max(0, Math.floor((total - 1) / IDEAS_PAGE_SIZE) * IDEAS_PAGE_SIZE));
    }
  }, [ideas.length, list.isPlaceholderData, list.isSuccess, offset, total]);

  const selected = detail.data?.idea ?? null;
  const unfiltered = !status && offset === 0;

  return (
    <div className="mx-auto w-full max-w-page animate-fade-up">
      <PageHeader
        eyebrow="Research lab"
        icon={Lightbulb}
        title="Ideas"
        description="Your private backlog of video ideas. Research each one with real YouTube data, check demand, and carry the strongest into a package."
        actions={
          <>
            {list.isSuccess && unfiltered ? (
              <EvidenceChip tone="info">
                {total} {total === 1 ? "idea" : "ideas"}
              </EvidenceChip>
            ) : null}
            <Button variant="gradient" onClick={() => setFormOpen(true)}>
              <Plus aria-hidden="true" />
              New idea
            </Button>
          </>
        }
      />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[23rem_minmax(0,1fr)]">
        <IdeaList
          ideas={ideas}
          total={total}
          offset={offset}
          status={status}
          onStatusChange={(next) => {
            setStatus(next);
            setOffset(0);
          }}
          onOffsetChange={setOffset}
          isPending={list.isPending}
          isFetching={list.isFetching}
          error={list.error}
          selectedId={selectedId}
          onSelect={select}
          onRefresh={() => void list.refetch()}
        />
        <div ref={detailRef} className="min-w-0 scroll-mt-24">
          <IdeaDetail
            idea={selected}
            isLoading={detail.isPending && selectedId !== null}
            error={detail.error}
            hasSelection={selectedId !== null}
            // Offer the first-idea prompt only once the backlog is known to be empty.
            hasIdeas={!(list.isSuccess && unfiltered && total === 0)}
            onNewIdea={() => setFormOpen(true)}
          />
        </div>
      </div>

      <IdeaFormSheet
        open={formOpen}
        onOpenChange={setFormOpen}
        onCreated={(idea) => {
          // Show the new idea where it lands: first on the unfiltered list.
          setStatus("");
          setOffset(0);
          select(idea.id);
        }}
      />
    </div>
  );
}
