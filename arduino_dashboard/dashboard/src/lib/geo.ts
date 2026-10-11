import { INTERSECTIONS } from "../data/intersections";

const EARTH_RADIUS_M = 6_371_008.8;

/** Distance in meters between two geographic points (haversine formula). */
export function distanceM(
  a: { lat: number; lng: number },
  b: { lat: number; lng: number },
): number {
  const φ1 = (a.lat * Math.PI) / 180;
  const φ2 = (b.lat * Math.PI) / 180;
  const Δφ = φ2 - φ1;
  const Δλ = ((b.lng - a.lng) * Math.PI) / 180;
  const s =
    Math.sin(Δφ / 2) ** 2 + Math.cos(φ1) * Math.cos(φ2) * Math.sin(Δλ / 2) ** 2;
  return 2 * EARTH_RADIUS_M * Math.asin(Math.min(1, Math.sqrt(s)));
}

/** Length of the corridor, summed leg by leg between the OSM nodes of the intersections. */
export function corridorTotalM(): number {
  let total = 0;
  for (let i = 0; i < INTERSECTIONS.length - 1; i++) {
    total += distanceM(INTERSECTIONS[i], INTERSECTIONS[i + 1]);
  }
  return total;
}
