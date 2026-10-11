import { useEffect, useId, useRef, useState, type ReactNode } from "react";

interface PopoverProps {
  /** Text of the button that opens the panel. */
  label: string;
  /** Extra class for the button. */
  buttonClass?: string;
  children: ReactNode;
}

/**
 * A button that opens a small panel of help text. It opens with a click, a tap
 * or the keyboard, closes on Escape or an outside click, and returns focus to
 * the button: nothing here depends on hovering.
 */
export function Popover({ label, buttonClass = "", children }: PopoverProps) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLSpanElement | null>(null);
  const panelId = useId();

  useEffect(() => {
    if (!open) return;
    const onDown = (e: PointerEvent) => {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        wrapRef.current?.querySelector<HTMLButtonElement>("button")?.focus();
      }
    };
    document.addEventListener("pointerdown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <span className="pop-wrap" ref={wrapRef}>
      <button
        type="button"
        className={`pop-button ${buttonClass}`.trim()}
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((o) => !o)}
      >
        {label}
      </button>
      <span id={panelId} className="pop-panel" role="note" hidden={!open}>
        {children}
      </span>
    </span>
  );
}
