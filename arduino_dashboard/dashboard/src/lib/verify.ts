import type { VehicleClass } from "../data/types";

const OPERATOR_KEY = "larp.operator.v1";

/** Key of an hourly row to verify. */
export function anomalyKey(nodeId: string, ts: number, cls: VehicleClass): string {
  return `${nodeId}:${ts}:${cls}`;
}

export function loadOperator(): string {
  if (typeof localStorage === "undefined") return "";
  try {
    return localStorage.getItem(OPERATOR_KEY) ?? "";
  } catch {
    return "";
  }
}

export function saveOperator(name: string): void {
  if (typeof localStorage === "undefined") return;
  try {
    localStorage.setItem(OPERATOR_KEY, name);
  } catch {
    /* no storage: the operator name stays valid for the session */
  }
}
