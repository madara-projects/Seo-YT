import { useCallback, useEffect, useRef, useState } from "react";
import { Check, Copy, X } from "lucide-react";
import { toast } from "sonner";
import { Button, type ButtonProps } from "@/components/ui/button";

/**
 * Copy-to-clipboard with the legacy fallback preserved: `navigator.clipboard`
 * is unavailable on insecure origins, and this app is routinely served over
 * plain http on a LAN address, so the textarea+execCommand path still matters.
 */
async function writeToClipboard(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    /* fall through to the legacy path */
  }

  try {
    const area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    const copied = document.execCommand("copy");
    area.remove();
    return copied;
  } catch {
    return false;
  }
}

interface CopyButtonProps extends Omit<ButtonProps, "onClick" | "value"> {
  value: string;
  label?: string;
  successMessage?: string;
}

export function CopyButton({
  value,
  label = "Copy",
  successMessage = "Copied to clipboard.",
  variant = "outline",
  size = "sm",
  ...props
}: CopyButtonProps) {
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");
  const timer = useRef<number>();

  useEffect(() => () => window.clearTimeout(timer.current), []);

  const handleCopy = useCallback(async () => {
    if (!value) {
      toast.error("Nothing is available to copy.");
      return;
    }
    const copied = await writeToClipboard(value);
    setState(copied ? "copied" : "failed");
    if (copied) toast.success(successMessage);
    else toast.error("Clipboard access failed. Select and copy the text manually.");

    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setState("idle"), 1500);
  }, [value, successMessage]);

  const Icon = state === "copied" ? Check : state === "failed" ? X : Copy;

  return (
    <Button variant={variant} size={size} onClick={handleCopy} {...props}>
      <Icon aria-hidden="true" className={state === "copied" ? "text-tone-ok" : undefined} />
      {state === "copied" ? "Copied" : state === "failed" ? "Copy failed" : label}
    </Button>
  );
}
