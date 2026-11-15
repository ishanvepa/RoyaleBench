import { Check, Copy } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/cn";
import { Button } from "./button";

interface CodeBlockProps {
  code: string;
  /** Shown top-left, for example a file name. */
  label?: string;
  className?: string;
  /** Cap the height and scroll. */
  maxHeight?: string;
  /** Wrap long lines instead of scrolling sideways. */
  wrap?: boolean;
}

export function CodeBlock({ code, label, className, maxHeight, wrap = false }: CodeBlockProps) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  useEffect(() => () => clearTimeout(timer.current), []);

  async function copy() {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      clearTimeout(timer.current);
      timer.current = setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard access can be blocked (insecure origin, permissions); the text is still selectable.
    }
  }

  return (
    <div className={cn("overflow-hidden rounded-lg border border-line bg-surface", className)}>
      <div className="flex items-center justify-between border-b border-line px-3 py-1.5">
        <span className="truncate font-mono text-xs text-muted">{label ?? ""}</span>
        <Button variant="ghost" size="sm" onClick={copy} aria-label={copied ? "Copied" : "Copy to clipboard"} className="-mr-1.5 h-7">
          {copied ? <Check className="size-3.5" aria-hidden /> : <Copy className="size-3.5" aria-hidden />}
          {copied ? "Copied" : "Copy"}
        </Button>
      </div>
      <pre
        className={cn("overflow-auto p-3 font-mono text-xs leading-relaxed text-ink", wrap ? "whitespace-pre-wrap break-words" : "")}
        style={maxHeight ? { maxHeight } : undefined}
        tabIndex={0}
      >
        <code>{code}</code>
      </pre>
    </div>
  );
}
