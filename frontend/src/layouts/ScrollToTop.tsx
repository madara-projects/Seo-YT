import { useEffect } from "react";
import { useLocation } from "react-router-dom";

/**
 * Resets scroll on navigation.
 *
 * The legacy shell did this explicitly (`switchPage` set the container's
 * scrollTop to 0). React Router does not scroll-restore by default, so
 * without this, moving from a long History list to the Dashboard lands the
 * user mid-page — a regression that is easy to notice and hard to attribute.
 */
export function ScrollToTop() {
  const { pathname } = useLocation();

  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: "instant" as ScrollBehavior });
  }, [pathname]);

  return null;
}
