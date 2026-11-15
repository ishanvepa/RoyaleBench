import { useEnvironment } from "./api/environment";

export interface StartAbility {
  /** True when starting, stopping and publishing can work right now. */
  allowed: boolean;
  /** Why not, in a sentence, when it is not allowed. */
  reason: string | null;
  loading: boolean;
}

/**
 * Whether actions that spend credits are available: the server must not be read-only, Valkyrie must be reachable
 * and signed in, and Modal must be connected as the sandbox provider.
 */
export function useCanStart(): StartAbility {
  const { data: env, isPending } = useEnvironment();
  if (isPending) return { allowed: false, reason: "Checking the Valkyrie connection…", loading: true };
  if (!env) return { allowed: false, reason: "Cannot reach the RoyaleBench server.", loading: false };
  if (env.read_only) return { allowed: false, reason: "This server is read-only.", loading: false };
  if (!env.valkyrie_ok) return { allowed: false, reason: env.valkyrie_error ?? "Valkyrie is not reachable.", loading: false };
  if (!env.modal_configured) return { allowed: false, reason: "Modal is not connected as a sandbox provider in Valkyrie.", loading: false };
  return { allowed: true, reason: null, loading: false };
}
