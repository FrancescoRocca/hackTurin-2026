import { Popover } from "./Popover";

/** Lists the keyboard shortcuts, which are otherwise invisible. */
export function ShortcutsButton() {
  return (
    <Popover label="Keys" buttonClass="keys-button">
      <dl className="keys-list">
        <dt>
          <kbd>↑</kbd> <kbd>↓</kbd> <kbd>Home</kbd> <kbd>End</kbd>
        </dt>
        <dd>Move through the intersections</dd>
        <dt>
          <kbd>N</kbd>
        </dt>
        <dd>Next intersection to review</dd>
        <dt>
          <kbd>P</kbd>
        </dt>
        <dd>Pause or resume</dd>
      </dl>
    </Popover>
  );
}
