import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router";
import { z } from "zod";

/** A boolean URL parameter: absent or anything else is false; "1" and "true" are true. */
export const boolParam = () =>
  z
    .string()
    .optional()
    .transform((v) => v === "1" || v === "true")
    .catch(false);

/** A string URL parameter that falls back to ``fallback`` when absent or invalid. */
export const stringParam = (fallback = "") => z.string().optional().catch(undefined).transform((v) => v ?? fallback);

/** A string that must be one of ``values``, else ``fallback``. */
export const enumParam = <const V extends readonly [string, ...string[]]>(values: V, fallback: V[number]) =>
  z.enum(values).optional().catch(undefined).transform((v) => v ?? fallback);

/** Comma-separated list parameter ("a,b") as an array. */
export const listParam = () =>
  z
    .string()
    .optional()
    .catch(undefined)
    .transform((v) => (v ? v.split(",").filter(Boolean) : []));

/**
 * Page state that lives in the URL, so a filtered or sorted view can be bookmarked, shared and reloaded.
 *
 * The schema must accept an empty object (give every field a fallback); values that equal their fallback are
 * left out of the URL to keep links short. Updates replace the history entry by default so typing in a filter
 * does not fill the back button.
 */
export function useSearchState<T extends Record<string, unknown>>(schema: z.ZodType<T>) {
  const [params, setParams] = useSearchParams();
  const value = useMemo(() => schema.parse(Object.fromEntries(params.entries())), [schema, params]);
  const defaults = useMemo(() => schema.parse({}) as Record<string, unknown>, [schema]);

  const update = useCallback(
    (patch: Partial<T>, options?: { replace?: boolean }) => {
      setParams(
        (previous) => {
          const next = new URLSearchParams(previous);
          for (const [key, raw] of Object.entries(patch)) {
            const serialised = Array.isArray(raw) ? raw.join(",") : raw;
            const fallback = Array.isArray(defaults[key]) ? (defaults[key] as unknown[]).join(",") : defaults[key];
            if (serialised === undefined || serialised === null || serialised === "" || serialised === fallback) next.delete(key);
            else next.set(key, String(serialised));
          }
          return next;
        },
        { replace: options?.replace ?? true },
      );
    },
    [defaults, setParams],
  );

  return [value, update] as const;
}
