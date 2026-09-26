import { useCallback, useRef } from "react";

/**
 * Returns focus to whatever had it when a dialog opened. Radix does this only
 * through a `Dialog.Trigger`, but the app's dialogs and sheets open from state
 * (a row's button, a keyboard shortcut), so focus fell to <body> on close and
 * a keyboard user started again from the top of the page.
 *
 * Pass the caller's own handlers through; one that prevents the default keeps
 * control of focus.
 */
export function useFocusReturn(
  onOpenAutoFocus?: (event: Event) => void,
  onCloseAutoFocus?: (event: Event) => void,
) {
  const opener = useRef<HTMLElement | null>(null);

  const handleOpen = useCallback(
    (event: Event) => {
      // Radix fires this before it moves focus, so the opener still has it.
      const active = document.activeElement;
      opener.current = active instanceof HTMLElement && active !== document.body ? active : null;
      onOpenAutoFocus?.(event);
    },
    [onOpenAutoFocus],
  );

  const handleClose = useCallback(
    (event: Event) => {
      onCloseAutoFocus?.(event);
      const target = opener.current;
      opener.current = null;
      // An opener that has gone (its page was left) can't take focus back.
      if (event.defaultPrevented || !target?.isConnected) return;
      event.preventDefault();
      target.focus({ preventScroll: true });
    },
    [onCloseAutoFocus],
  );

  return { onOpenAutoFocus: handleOpen, onCloseAutoFocus: handleClose };
}
