import { Video } from "@remotion/media";
import {
  CanvasImage,
  Interactive,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { body, ink, lime, orange, paper } from "./design";

type Source = "opus" | "reference";
type Camera = "full" | "defense" | "attack";

// A camera crops the recorded pixels only. Engine state and replay timing are
// unchanged. Time/HP overlays are computed evidence and intentionally read-only.
export const Replay = ({
  source,
  camera = "full",
  start = 0,
  speed = 1,
  freeze,
  style,
}: {
  source: Source;
  camera?: Camera;
  start?: number;
  speed?: number;
  freeze?: number;
  style?: React.CSSProperties;
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  // Preserve the recorded game clock, but let the shared renderer's ending play
  // for another 1.8 seconds before holding its settled result frame.
  const duration = (source === "opus" ? 10.35 : 11.2) + 1.8;
  const ended = (frame / fps) * speed + start >= duration;
  const still = freeze;
  // Full source is 486x866. Defense shows the lower half; attack the upper half.
  const sizing: React.CSSProperties = { width: "100%", height: "100%" };
  const cameraStyle: React.CSSProperties =
    camera === "full"
      ? { width: "100%", height: "100%" }
      : {
          width: "100%",
          aspectRatio: "486 / 866",
          position: "absolute",
          left: 0,
          ...(camera === "defense" ? { bottom: "-40%" } : { top: 0 }),
        };
  return (
    <div
      style={{
        position: "relative",
        overflow: "hidden",
        background: ink,
        ...style,
      }}
    >
      <div style={cameraStyle}>
        {still === undefined && !ended ? (
          <Video
            name="Recorded gameplay"
            src={staticFile(
              `media/${source}-${camera === "full" ? "ending" : "impact"}.mp4`,
            )}
            trimBefore={Math.round(start * fps)}
            playbackRate={speed}
            muted
            objectFit="contain"
            style={sizing}
          />
        ) : (
          <CanvasImage
            name="Recorded freeze frame"
            src={staticFile(
              still === undefined
                ? `media/${source}-${camera === "full" ? "ending" : "impact"}-final.png`
                : `media/${source}-${String(still).padStart(4, "0")}.png`,
            )}
            style={sizing}
          />
        )}
      </div>
    </div>
  );
};

export const Clock = ({
  start = 0,
  speed = 1,
  source = "opus",
}: {
  start?: number;
  speed?: number;
  source?: Source;
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const time = Math.min(
    source === "opus" ? 10.35 : 11.2,
    start + (frame / fps) * speed,
  );
  return (
    <div
      style={{
        fontFamily: body,
        fontSize: 34,
        fontWeight: 700,
        fontVariantNumeric: "tabular-nums",
        color: paper,
      }}
    >
      REPLAY&nbsp; / &nbsp;{time.toFixed(2)}s
    </div>
  );
};

export const Marker = ({
  x,
  y,
  width = 160,
  height = 100,
  color = orange,
}: {
  x: number;
  y: number;
  width?: number;
  height?: number;
  color?: string;
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <svg
      width="1920"
      height="1080"
      viewBox="0 0 1920 1080"
      style={{ position: "absolute", inset: 0, pointerEvents: "none" }}
    >
      <ellipse
        cx={x}
        cy={y}
        rx={width / 2}
        ry={height / 2}
        fill="none"
        stroke={color}
        strokeWidth="8"
        strokeDasharray="1"
        pathLength="1"
        strokeDashoffset={interpolate(frame, [0, 0.45 * fps], [1, 0], {
          extrapolateRight: "clamp",
        })}
        transform={`rotate(-7 ${x} ${y})`}
      />
    </svg>
  );
};

export const Badge = ({
  children,
  accent = false,
}: {
  children: React.ReactNode;
  accent?: boolean;
}) => (
  <div
    style={{
      display: "inline-block",
      fontFamily: body,
      fontSize: 32,
      fontWeight: 700,
      background: accent ? lime : ink,
      color: accent ? ink : paper,
      padding: "14px 24px",
      textTransform: "uppercase",
    }}
  >
    {children}
  </div>
);

export const Shot = Interactive.create({
  Component: ({
    source,
    camera,
    start,
    speed,
    style,
  }: {
    source: Source;
    camera: Camera;
    start: number;
    speed: number;
    style: React.CSSProperties;
  }) => (
    <Replay
      source={source}
      camera={camera}
      start={start}
      speed={speed}
      style={{ width: "100%", height: "100%", ...style }}
    />
  ),
  layout: "none",
  schema: {
    source: {
      type: "enum",
      default: "opus",
      description: "Recorded source",
      variants: { opus: {}, reference: {} },
    },
    camera: {
      type: "enum",
      default: "full",
      description: "Camera crop",
      variants: { full: {}, defense: {}, attack: {} },
    },
    start: {
      type: "number",
      default: 0,
      description: "Source start in seconds",
      min: 0,
      max: 11,
      hiddenFromList: false,
    },
    speed: {
      type: "number",
      default: 1,
      description: "Playback speed",
      min: 0.25,
      max: 2,
      hiddenFromList: false,
    },
  },
});
