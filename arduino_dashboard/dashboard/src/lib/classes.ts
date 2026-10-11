import { CLASS_LABEL, VEHICLE_CLASSES, type VehicleClass } from "../data/types";

/** Presentation order, the same everywhere: list, charts, legend. */
export const CLASS_ORDER: VehicleClass[] = [...VEHICLE_CLASSES];

/**
 * One color for each of the four classes, and only for classes: it lives where
 * there is data (bars, chart columns, legend). States use other colors.
 */
export const CLASS_PEN: Record<VehicleClass, string> = {
  car: "var(--pen-car)",
  bicycle: "var(--pen-bicycle)",
  motorcycle: "var(--pen-motorcycle)",
  pedestrian: "var(--pen-pedestrian)",
};

/** Plural, for sentences: "223 bicycles passed". */
export const CLASS_PLURAL: Record<VehicleClass, string> = {
  car: "cars",
  bicycle: "bicycles",
  motorcycle: "motorcycles",
  pedestrian: "pedestrians",
};

export { CLASS_LABEL };
export type { VehicleClass };
