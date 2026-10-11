/** The shape of the page while the sensors respond: no invented numbers. */
export function LoadingSkeleton() {
  return (
    <div className="skeleton-page" aria-busy="true">
      <p className="sr" role="status">
        Reading sensors…
      </p>
      <div className="summary" aria-hidden="true">
        {[0, 1, 2].map((i) => (
          <div className="sum skeleton" key={i}>
            <i style={{ width: "46%" }} />
            <i style={{ width: "64%", height: 26 }} />
            <i style={{ width: "80%" }} />
          </div>
        ))}
      </div>
      <div className="work" aria-hidden="true">
        <div className="panel skeleton-panel" />
        <div className="panel skeleton-panel" />
        <div className="panel skeleton-panel" />
      </div>
    </div>
  );
}
