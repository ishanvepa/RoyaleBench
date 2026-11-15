import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { body, lime, orange, paper } from "./design";

// The recorded deployment ticks are identical in both replays: 0, 2, …, 10s.
// This rail describes those events; it does not retime the footage.
export const ActionRail = ({ reference = false }: { reference?: boolean }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const active = Math.min(5, Math.floor(frame / fps / 2));
  const accent = reference ? lime : orange;
  return (
    <div style={{ position: "absolute", left: 690, top: 906, width: 1120 }}>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(6, 1fr)",
          gap: 12,
        }}
      >
        {[
          "Ice Spirits",
          "Cannon",
          "Fireball",
          "Hog Rider",
          "Log",
          "Ice Spirits",
        ].map((card, i) => (
          <div key={i} style={{ fontFamily: body }}>
            <div style={{ height: 3, background: "#44463f", marginBottom: 14 }}>
              <div
                style={{
                  height: "100%",
                  background: accent,
                  width: `${interpolate(frame, [i * 2 * fps, (i * 2 + 0.35) * fps], [0, 100], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })}%`,
                }}
              />
            </div>
            <div
              style={{
                color: i === active ? accent : paper,
                opacity: i > active ? 0.4 : 1,
                fontSize: 23,
                fontWeight: 700,
              }}
            >
              <span
                style={{
                  fontSize: 19,
                  marginRight: 8,
                  color: i === active ? accent : "#a6a89c",
                }}
              >
                {String(i + 1).padStart(2, "0")}
              </span>
              {card}
            </div>
          </div>
        ))}
      </div>
      <div
        style={{ marginTop: 21, color: paper, fontFamily: body, fontSize: 30 }}
      >
        {active === 0
          ? "Freeze the incoming Giant."
          : active === 1
            ? reference
              ? "Cannon placed higher and closer to the left lane."
              : "Cannon placed lower and farther from the left lane."
            : active === 2
              ? "Fireball chips the enemy tower."
              : active === 3
                ? "Hog Rider goes on offense."
                : active === 4
                  ? reference
                    ? "Log targets the Giant on defense."
                    : "Log targets the enemy tower."
                  : reference
                    ? frame / fps < 11.2
                      ? "Final Ice Spirits. Watch the Hog."
                      : "The Hog connects. Our tower stays up."
                    : frame / fps < 10.35
                      ? "Final Ice Spirits on defense."
                      : "The Giant gets through first."}
      </div>
    </div>
  );
};
