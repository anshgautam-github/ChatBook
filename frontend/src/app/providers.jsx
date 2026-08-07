import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "@/lib/queryClient";

/**
 * Wraps the app with global providers (React Query now; auth/theme later).
 */
export function AppProviders({ children }) {
  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}
