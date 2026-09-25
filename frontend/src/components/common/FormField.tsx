import { useId } from "react";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

/**
 * A labelled form control with its validation message, or a hint when valid.
 * The message is an alert so it is announced as soon as it appears.
 */
export function FormField({
  id,
  label,
  hint,
  error,
  optional = false,
  className,
  children,
}: {
  id: string;
  label: string;
  hint?: string;
  error?: string;
  optional?: boolean;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div className={cn("space-y-2", className)}>
      <Label htmlFor={id} className="flex items-baseline gap-1.5">
        {label}
        {optional ? <span className="text-xs font-normal text-muted-foreground">Optional</span> : null}
      </Label>
      {children}
      {error ? (
        <p role="alert" className="text-xs font-medium text-tone-bad">
          {error}
        </p>
      ) : hint ? (
        <p className="text-xs leading-relaxed text-muted-foreground">{hint}</p>
      ) : null}
    </div>
  );
}

/** A titled group of fields inside a long form. */
export function FormSection({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  const descriptionId = useId();
  return (
    // The legend must be the fieldset's first child to name the group.
    <fieldset className="space-y-4" aria-describedby={description ? descriptionId : undefined}>
      <legend className="font-display text-sm font-semibold text-foreground">{title}</legend>
      {description ? (
        <p id={descriptionId} className="-mt-3 text-xs leading-relaxed text-muted-foreground">
          {description}
        </p>
      ) : null}
      {children}
    </fieldset>
  );
}
