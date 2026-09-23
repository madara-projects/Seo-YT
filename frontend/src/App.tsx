import { lazy, Suspense, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";

import { AppShell } from "@/layouts/AppShell";
import { ScrollToTop } from "@/layouts/ScrollToTop";
import { ThemeProvider, useTheme } from "@/lib/theme";
import { TooltipProvider } from "@/components/ui/tooltip";
import { CardSkeleton } from "@/components/common/States";
import CreatorPage from "@/pages/Creator";

const DashboardPage = lazy(() => import("@/pages/Dashboard"));
const HistoryPage = lazy(() => import("@/pages/History"));
const IdeasPage = lazy(() => import("@/pages/Ideas"));
const DemandPage = lazy(() => import("@/pages/Demand"));
const AuditsPage = lazy(() => import("@/pages/Audits"));
const ExperimentsPage = lazy(() => import("@/pages/Experiments"));
const WatchlistPage = lazy(() => import("@/pages/Watchlist"));
const SettingsPage = lazy(() => import("@/pages/Settings"));

export function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // Local backend, single user: refetching on every focus is noise, and
        // several of these endpoints are rate-limited per path.
        refetchOnWindowFocus: false,
        staleTime: 30_000,
        retry: 1,
      },
    },
  });
}

function ThemedToaster() {
  const { resolvedTheme } = useTheme();
  return <Toaster theme={resolvedTheme} position="bottom-right" richColors closeButton />;
}

export function App() {
  // One client per App instance rather than a module-level singleton: the app
  // mounts once, and tests each get a clean cache instead of inheriting
  // whatever a previous test left behind.
  const [queryClient] = useState(createQueryClient);

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <TooltipProvider delayDuration={200}>
          <ScrollToTop />
          <Routes>
            <Route element={<AppShell />}>
              <Route index element={<Navigate to="/creator" replace />} />
              <Route path="/creator" element={<CreatorPage />} />
              <Route
                path="/*"
                element={
                  <Suspense fallback={<CardSkeleton rows={4} />}>
                    <Routes>
                      <Route path="/dashboard" element={<DashboardPage />} />
                      <Route path="/history" element={<HistoryPage />} />
                      <Route path="/ideas" element={<IdeasPage />} />
                      <Route path="/demand" element={<DemandPage />} />
                      <Route path="/audits" element={<AuditsPage />} />
                      <Route path="/experiments" element={<ExperimentsPage />} />
                      <Route path="/watchlist" element={<WatchlistPage />} />
                      <Route path="/settings" element={<SettingsPage />} />
                      <Route path="*" element={<Navigate to="/creator" replace />} />
                    </Routes>
                  </Suspense>
                }
              />
            </Route>
          </Routes>
          <ThemedToaster />
        </TooltipProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
