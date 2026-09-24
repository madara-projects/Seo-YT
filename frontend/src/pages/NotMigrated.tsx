import { ArrowUpRight, Construction, FlaskConical } from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/common/States";

/**
 * Honest placeholder for pages still served by the legacy dashboard.
 * It links to the working implementation rather than showing a dead shell.
 */
export function NotMigrated({
  title,
  description,
  legacyHash,
}: {
  title: string;
  description: string;
  legacyHash: string;
}) {
  return (
    <div className="mx-auto w-full max-w-4xl animate-fade-up">
      <PageHeader eyebrow="Research lab" icon={FlaskConical} title={title} description={description} />
      <EmptyState
        icon={Construction}
        title="Not migrated yet"
        description="This page still runs in the classic dashboard, which keeps working in a new tab. It will move into this workspace with the same components as Creator, Dashboard and History."
        action={
          <Button variant="outline" asChild>
            <a href={`/dashboard_legacy${legacyHash}`} target="_blank" rel="noreferrer">
              Open in legacy dashboard
              <ArrowUpRight aria-hidden="true" />
            </a>
          </Button>
        }
      />
    </div>
  );
}
