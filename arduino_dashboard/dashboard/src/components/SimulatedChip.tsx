import { Popover } from "./Popover";

/** The "Simulated data" badge, with its explanation one click away. */
export function SimulatedChip() {
  return (
    <Popover label="Simulated data" buttonClass="chip">
      There are no sensors connected yet: every count is generated for the demo. When the real
      feed is live, this badge disappears.
    </Popover>
  );
}
