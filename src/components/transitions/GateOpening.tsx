import { useEffect } from "react";
import "./gate-opening.css";

type GateOpeningProps = {
  onComplete: () => void;
};

const TOTAL_DURATION = 2200;

export function GateOpening({ onComplete }: GateOpeningProps) {
  useEffect(() => {
    const timer = window.setTimeout(() => {
      onComplete();
    }, TOTAL_DURATION);

    return () => window.clearTimeout(timer);
  }, [onComplete]);

  return (
    <div className="kairos-gate-overlay" aria-hidden="true">
      <div className="kairos-main-image-opening">
        <div className="kairos-image-panel kairos-image-panel-left" />
        <div className="kairos-image-panel kairos-image-panel-right" />
        <div className="kairos-image-seam-glow" />
      </div>
    </div>
  );
}