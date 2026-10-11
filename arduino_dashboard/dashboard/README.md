# larp dashboard

Operations console for the **larp** nodes (Arduino UNO Q + IMX219) installed along
Corso Bolzano in Turin, near Porta Susa.

It answers two questions: *is the network alive?* and *what passed through this
intersection today?* There are six intersections, anchored to real OpenStreetMap
nodes (extracted with Overpass by intersecting ways on shared nodes), from the
bridge over the Dora Riparia up to Piazza XVIII Dicembre.

**The device transmits no images.** Classification happens on board and only
counts and metadata leave it. The dashboard shows no frames, invents none, and
states this in the header and in the detail of every intersection.

![The larp dashboard on simulated data](../docs/dashboard.png)

## Getting started

```bash
npm install
npm run dev         # http://localhost:5173
npm run build       # production build in dist/
npm run typecheck   # tsc --noEmit
```

## Data

There are no real detection logs in this repository. The network shown is a
**deterministic simulation**, labelled as such in the top bar ("Simulated data")
and at the bottom of each intersection's detail. The same day always produces the
same numbers; only the present keeps flowing.

Everything goes through a single seam, `TrafficSource` in `src/data/types.ts`:

| Implementation | File | Notes |
|---|---|---|
| `SimulatedSource` | `src/data/simulated.ts` | Hourly profile of an urban arterial road and a class mix per node. A few anomalies are planted so there is something to verify, and one node starts silent and resumes after 90 s. |
| `createHttpSource` | `src/data/adapter.ts` | Documented stub of the shape a real gateway must expose, including the SSE stream. |

To connect a real feed, change the active source at the bottom of `adapter.ts`.
No component knows where the numbers come from.

## What you see

Top to bottom, in the order an operator asks the questions:

- **Summary**: three tiles with active sensors, passes in the last 24 hours and
  unusual hours to review. The first and last tiles open the intersection that
  needs a look, and move to the next one on every click.
- **Intersections**: the six intersections as the stops of a line, north at the
  top as on the map. The number matches the map marker. State is shown by color,
  shape and text: filled circle is active, square with "!" needs review, hollow
  circle with "×" is not responding.
- **Map**: OpenStreetMap with the Corso Bolzano line and numbered markers.
- **Whole corridor, hour by hour**: all intersections summed, with a legend by
  type of pass.
- **Intersection detail**: sensor status, passes over 24 h, per minute and versus
  yesterday, what passed by type, the hourly chart, the hours to review and the
  latest passes.

An hour is **unusual** when the count for a class departs from the intersection's
own history (28-day baseline, more than 4 standard deviations). The operator
decides: "It's correct" or "It's a sensor error", with an optional note. The
verdict is stored in `localStorage` under `larp.verifications.v1` and can be
changed afterwards. It does not alter the displayed numbers.

### Keyboard

Also listed behind the **Keys** button in the top bar.

| Key | Action |
|---|---|
| `↑` `↓` `Home` `End` | Move through the intersection list |
| `N` | Jump to the next intersection that needs attention |
| `P` | Pause or resume the live feed |

## Layout

| Path | Contents |
|---|---|
| `src/App.tsx` | The page: top bar, summary, three columns, error and loading states |
| `src/components/` | Summary, intersection list, map, network chart, detail, hourly chart, verification |
| `src/data/` | Taxonomy, real intersections, simulation, HTTP seam |
| `src/lib/` | Formatting, geodesy, class colors and plurals, verification, node views |
| `src/styles.css` | Tokens and styles: midnight-blue bar, white panels, state and class colors |
| `public/fonts/` | Archivo and Righteous, served by the project |

## Accessibility

Full keyboard operation, visible focus rings, text contrast of at least 4.5:1,
state never carried by color alone, a skip link to the detail panel, a hidden
data table behind every chart, discreet `aria-live` announcements (a summary
every 20 seconds, plus any sensor that stops or resumes) and
`prefers-reduced-motion` respected.
