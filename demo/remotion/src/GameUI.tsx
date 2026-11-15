import type { CSSProperties, ReactNode } from "react";
import {
  AbsoluteFill,
  CanvasImage,
  Interactive,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { game, gameFont } from "./design";

export const plays = [
  { card: "IceSpirits", label: "Ice Spirits", cost: 1 },
  { card: "Cannon", label: "Cannon", cost: 3 },
  { card: "Fireball", label: "Fireball", cost: 4 },
  { card: "HogRider", label: "Hog Rider", cost: 4 },
  { card: "Log", label: "Log", cost: 2 },
  { card: "IceSpirits", label: "Ice Spirits", cost: 1 },
] as const;

export const cues = [
  { from: 0, to: 4, text: "RoyaleBench tests gameplay decisions by language models." },
  { from: 4, to: 8.5, text: "Each task begins from a fixed Clash Royale battle state." },
  { from: 8.5, to: 13, text: "The model reads text, chooses a card and coordinates; a verifier replays the actions." },
  { from: 13, to: 18, text: "Here is the actual text observation." },
  { from: 18, to: 24, text: "The model chooses a card slot and arena coordinates." },
  { from: 24, to: 28, text: "Same six cards. Same order, timing, and 15 elixir." },
  { from: 28, to: 33, text: "The placements differ." },
  { from: 33, to: 37, text: "Opus loses. The validated reference wins." },
  { from: 37, to: 43, text: "Reference Cannon: half a tile left, one tile higher." },
  { from: 43, to: 50, text: "Model Log: enemy tower. Reference Log: incoming Giant." },
  { from: 50, to: 59, text: "In the latest full v9 run, Opus completed 14 of 21 task objectives." },
  { from: 59, to: 63, text: "The validated reference finds the winning connection." },
] as const;

export const GameStage = ({ children }: { children: ReactNode }) => (
  <AbsoluteFill
    style={{
      backgroundColor: game.background,
      backgroundImage:
        "linear-gradient(#ffffff05 1px, transparent 1px), linear-gradient(90deg, #ffffff05 1px, transparent 1px)",
      backgroundSize: "72px 72px",
      color: game.text,
      fontFamily: gameFont,
      overflow: "hidden",
    }}
  >
    {children}
  </AbsoluteFill>
);

export const GameFrame = ({
  children,
  style,
  accent = game.blue,
}: {
  children: ReactNode;
  style: CSSProperties;
  accent?: string;
}) => (
  <div
    style={{
      overflow: "hidden",
      background: game.panel,
      border: `3px solid ${accent}`,
      borderRadius: 16,
      boxShadow: "0 18px 44px #0509149c, inset 0 0 0 4px #0e1420",
      ...style,
    }}
  >
    {children}
  </div>
);

export const GameTag = ({
  children,
  color = game.blue,
  style,
}: {
  children: ReactNode;
  color?: string;
  style?: CSSProperties;
}) => (
  <div
    style={{
      display: "inline-flex",
      alignItems: "center",
      border: `2px solid ${color}`,
      borderRadius: 8,
      background: game.surface,
      padding: "8px 15px",
      fontSize: 24,
      fontWeight: 800,
      letterSpacing: "0.04em",
      textTransform: "uppercase",
      boxShadow: "0 5px 14px #05091488",
      ...style,
    }}
  >
    {children}
  </div>
);

export const CardPortrait = ({
  card,
  width = 72,
  style,
}: {
  card: (typeof plays)[number]["card"];
  width?: number;
  style?: CSSProperties;
}) => (
  <div
    style={{
      width,
      height: (width * 60) / 48,
      border: `2px solid ${game.gold}`,
      borderRadius: 5,
      overflow: "hidden",
      boxShadow: "0 4px 8px #050914aa",
      ...style,
    }}
  >
    <CanvasImage
      src={staticFile(`cards/${card}.svg`)}
      style={{ width: "100%", height: "100%", imageRendering: "pixelated" }}
    />
  </div>
);

export const ElixirOrb = ({ cost }: { cost: number }) => (
  <span
    style={{
      display: "inline-grid",
      placeItems: "center",
      width: 40,
      height: 40,
      borderRadius: "50%",
      background: game.elixir,
      border: "2px solid #f7c7ff",
      color: "#fff",
      fontSize: 23,
      fontWeight: 900,
      textShadow: "0 2px 2px #67226f",
    }}
  >
    {cost}
  </span>
);

export const PlayStrip = ({ active }: { active: number }) => (
  <div style={{ display: "flex", gap: 9, justifyContent: "space-between" }}>
    {plays.map((play, index) => (
      <div
        key={index}
        style={{
          width: 74,
          padding: 4,
          borderRadius: 7,
          border: `2px solid ${index === active ? game.gold : game.line}`,
          background: index === active ? game.panel : game.surface,
          opacity: index > active ? 0.58 : 1,
          position: "relative",
        }}
      >
        <CardPortrait card={play.card} width={60} />
        <span
          style={{
            position: "absolute",
            right: -6,
            bottom: -8,
            borderRadius: "50%",
            background: game.elixir,
            border: "2px solid #f7c7ff",
            width: 26,
            height: 26,
            display: "grid",
            placeItems: "center",
            fontSize: 16,
            fontWeight: 800,
          }}
        >
          {play.cost}
        </span>
      </div>
    ))}
  </div>
);

export const CaptionTrack = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const seconds = frame / fps;
  const cue = cues.find((item) => seconds >= item.from && seconds < item.to);
  if (!cue) return null;
  return (
    <Interactive.Div
      name="Silent-viewing caption"
      style={{
        position: "absolute",
        zIndex: 20,
        left: 184,
        right: 184,
        bottom: 18,
        minHeight: 76,
        display: "grid",
        placeItems: "center",
        textAlign: "center",
        padding: "12px 30px",
        border: `2px solid ${game.line}`,
        borderLeft: `8px solid ${game.blue}`,
        borderRadius: 12,
        background: "#0e1420f2",
        boxShadow: "0 10px 30px #050914aa",
        color: game.text,
        fontFamily: gameFont,
        fontSize: 36,
        fontWeight: 700,
        lineHeight: 1.2,
      }}
    >
      {cue.text}
    </Interactive.Div>
  );
};
