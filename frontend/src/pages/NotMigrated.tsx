import { ExternalLink } from "lucide-react";
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
    <div className="mx-auto max-w-4xl">
      <PageHeader title={title} description={description} />
      <EmptyState
        title="Not migrated yet"
        description="This page still runs in the legacy dashboard. The React migration starts with Creator; this one follows the same component system."
        action={
          <Button variant="outline" asChild>
            <a href={`/dashboard_legacy${legacyHash}`} target="_blank" rel="noreferrer">
              <ExternalLink aria-hidden="true" />
              Open in legacy dashboard
            </a>
          </Button>
        }
      />
    </div>
  );
}
