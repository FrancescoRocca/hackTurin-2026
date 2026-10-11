import { useEffect, useRef } from "react";
import L from "leaflet";
import type { Intersection } from "../data/types";
import { CORRIDOR } from "../data/intersections";

export type MarkerState = "ok" | "warn" | "off";

interface PlanMapProps {
  nodes: Intersection[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  /**
   * State of each intersection. It must change identity only when a state
   * changes: markers are updated in place, not rebuilt.
   */
  states: Record<string, MarkerState>;
  /** Label of the selected node, e.g. "Via Grattoni · 13,221". */
  selectedLabel: string;
}

const STATE_TEXT: Record<MarkerState, string> = {
  ok: "active",
  warn: "needs review",
  off: "not responding",
};

/**
 * The real map of the area, with the Corso Bolzano line and the six
 * intersections numbered as in the list. Sensor state reads from the marker's
 * shape, not only its color: filled circle = active, square with "!" =
 * needs review, empty circle with "×" = not responding.
 *
 * Markers are created once and then updated in place, so the one-second tick
 * does not destroy them. They are not in the tab order: the intersection
 * list is the keyboard and screen-reader equivalent.
 */
export function PlanMap({ nodes, selectedId, onSelect, states, selectedLabel }: PlanMapProps) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const layerRef = useRef<L.LayerGroup | null>(null);
  const markersRef = useRef(new Map<string, L.Marker>());
  const labelRef = useRef(selectedLabel);
  labelRef.current = selectedLabel;
  const lastSelected = useRef<string | null>(null);
  const selectRef = useRef(onSelect);
  selectRef.current = onSelect;

  useEffect(() => {
    const host = hostRef.current;
    if (!host || mapRef.current) return;

    const map = L.map(host, { zoomControl: false, zoomSnap: 0.5, minZoom: 13, maxZoom: 18 });
    L.control.zoom({ position: "topright", zoomInTitle: "Zoom in", zoomOutTitle: "Zoom out" }).addTo(map);
    L.control.scale({ position: "bottomleft", imperial: false, maxWidth: 120 }).addTo(map);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);

    // The street line stays under the markers and never changes.
    const coords = CORRIDOR.map(([lat, lng]) => L.latLng(lat, lng));
    L.polyline(coords, { color: "#13233a", weight: 9, opacity: 0.14, lineCap: "round" }).addTo(map);
    L.polyline(coords, { color: "#13233a", weight: 2, opacity: 0.7 }).addTo(map);

    layerRef.current = L.layerGroup().addTo(map);
    map.fitBounds(L.latLngBounds(coords).pad(0.22), { animate: false });
    mapRef.current = map;

    const observer = new ResizeObserver(() => map.invalidateSize());
    observer.observe(host);
    return () => {
      observer.disconnect();
      map.remove();
      mapRef.current = null;
      layerRef.current = null;
      markersRef.current.clear();
    };
  }, []);

  // Markers are created when the list of intersections changes, never otherwise.
  useEffect(() => {
    const layer = layerRef.current;
    if (!layer) return;
    layer.clearLayers();
    markersRef.current.clear();

    nodes.forEach((node, index) => {
      const marker = L.marker([node.lat, node.lng], {
        icon: L.divIcon({
          className: "pin",
          html: `<span>${index + 1}</span>`,
          iconSize: [32, 32],
          iconAnchor: [16, 16],
        }),
        keyboard: false,
        riseOnHover: true,
      });
      marker.on("click", () => selectRef.current(node.id));
      marker.addTo(layer);
      markersRef.current.set(node.id, marker);
    });
    lastSelected.current = null;
  }, [nodes]);

  // State and selection: classes and text change on the element already present.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    nodes.forEach((node, index) => {
      const marker = markersRef.current.get(node.id);
      const el = marker?.getElement();
      if (!marker || !el) return;
      const state = states[node.id] ?? "off";
      const selected = node.id === selectedId;
      el.className = el.className
        .split(/\s+/)
        .filter((c) => c && !["ok", "warn", "off", "sel"].includes(c))
        .concat(state, selected ? ["sel"] : [])
        .join(" ");
      const text = `${index + 1}. ${node.name} — ${STATE_TEXT[state]}`;
      el.title = text;
      el.setAttribute("aria-hidden", "true");
      marker.setZIndexOffset(selected ? 1000 : 0);

      // The label goes on the side with more room ("auto" mirrors the offset). On
      // a narrow map there is no room: the name is already in the list beside it.
      const wantsLabel = selected && map.getSize().x >= 600;
      if (wantsLabel && !marker.getTooltip()) {
        marker.bindTooltip(labelRef.current, {
          permanent: true,
          direction: "auto",
          offset: [22, 0],
          className: "pin-label",
        });
      } else if (!wantsLabel && marker.getTooltip()) {
        marker.unbindTooltip();
      }
    });

    const selectedNode = nodes.find((n) => n.id === selectedId);
    if (selectedNode && lastSelected.current !== selectedId) {
      const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
      map.panInside([selectedNode.lat, selectedNode.lng], { animate: !reduced, duration: 0.4, padding: [80, 80] });
    }
    lastSelected.current = selectedId;
  }, [nodes, selectedId, states]);

  // The number on the label keeps moving: update the text, not the marker.
  useEffect(() => {
    if (!selectedId) return;
    markersRef.current.get(selectedId)?.getTooltip()?.setContent(selectedLabel);
  }, [selectedId, selectedLabel]);

  return (
    <section className="panel mapbox" aria-label="Intersection map">
      <div className="map-canvas" ref={hostRef} />
      <div className="map-key" aria-hidden="true">
        <span><i className="pin-key ok" /> active</span>
        <span><i className="pin-key warn" /> needs review</span>
        <span><i className="pin-key off" /> not responding</span>
      </div>
    </section>
  );
}
