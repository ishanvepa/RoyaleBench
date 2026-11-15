import { render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RouterProvider } from "react-router";
import { Providers } from "@/app/providers";
import { createQueryClient } from "@/app/queryClient";
import { createTestRouter } from "@/app/routes";

/** Render the real app at ``path`` with a fresh, non-retrying query client and an in-memory router. */
export function renderApp(path: string) {
  const client = createQueryClient();
  client.setDefaultOptions({ queries: { retry: false, staleTime: 0, gcTime: 0, refetchOnWindowFocus: false } });
  const router = createTestRouter(path);
  const user = userEvent.setup();
  const view = render(
    <Providers client={client}>
      <RouterProvider router={router} />
    </Providers>,
  );
  return { router, client, user, ...view };
}
