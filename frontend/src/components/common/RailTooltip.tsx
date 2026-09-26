import { cloneElement, useState } from "react";
import { createPortal } from "react-dom";

type Handler<E> = ((event: E) => void) | undefined;

function both<E>(first: Handler<E>, second: (event: E) => void) {
  return (event: E) => {
    first?.(event);
    second(event);
  };
}

interface AnchorProps {
  onPointerEnter?: (event: React.PointerEvent<HTMLElement>) => void;
  onPointerLeave?: (event: React.PointerEvent<HTMLElement>) => void;
  onFocus?: (event: React.FocusEvent<HTMLElement>) => void;
  onBlur?: (event: React.FocusEvent<HTMLElement>) => void;
  onKeyDown?: (event: React.KeyboardEvent<HTMLElement>) => void;
}

/**
 * The name of an icon-only control in the collapsed sidebar, shown beside it
 * on hover and on keyboard focus. Rendered in a portal because the rail
 * clips its overflow. The control already carries the name for assistive
 * technology, so the bubble is hidden from it; Escape dismisses it.
 */
export function RailTooltip({
  label,
  enabled,
  children,
}: {
  label: string;
  enabled: boolean;
  children: React.ReactElement<AnchorProps>;
}) {
  const [anchor, setAnchor] = useState<DOMRect | null>(null);
  if (!enabled) return children;

  const show = (event: { currentTarget: HTMLElement }) => setAnchor(event.currentTarget.getBoundingClientRect());
  const hide = () => setAnchor(null);
  const props = children.props;

  return (
    <>
      {cloneElement(children, {
        onPointerEnter: both(props.onPointerEnter, show),
        onPointerLeave: both(props.onPointerLeave, hide),
        onFocus: both(props.onFocus, show),
        onBlur: both(props.onBlur, hide),
        onKeyDown: both(props.onKeyDown, (event: React.KeyboardEvent<HTMLElement>) => {
          if (event.key === "Escape") hide();
        }),
      })}
      {anchor
        ? createPortal(
            <span
              aria-hidden="true"
              data-testid="rail-tooltip"
              className="pointer-events-none fixed z-[70] -translate-y-1/2 whitespace-nowrap rounded-lg bg-popover px-2.5 py-1.5 text-xs font-medium text-popover-foreground shadow-elevated ring-1 ring-border"
              style={{ top: anchor.top + anchor.height / 2, left: anchor.right + 10 }}
            >
              {label}
            </span>,
            document.body,
          )
        : null}
    </>
  );
}
