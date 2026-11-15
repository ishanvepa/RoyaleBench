import type { CSSProperties } from "react";

export const paper = "#f3efe5";
export const ink = "#191b17";
export const orange = "#ec4a2e";
export const lime = "#d0ed58";
export const body = "Arial, Helvetica, sans-serif";
export const display = "ReplayDisplay, Impact, sans-serif";
export const headline: CSSProperties = {
  fontFamily: display,
  fontWeight: 400,
  textTransform: "uppercase",
  lineHeight: 0.96,
  letterSpacing: "-0.025em",
  margin: 0,
};

// Shared replay and live-play colors from cr_arena/replay.html and
// cr_arena/battle_renderer.js. The v03 aliases above stay for its archived edit.
export const game = {
  background: "#0e1420",
  surface: "#172033",
  panel: "#1f2b44",
  line: "#354563",
  text: "#e8edf7",
  muted: "#a5b2c9",
  blue: "#3b8ef0",
  red: "#f0703c",
  gold: "#f2c230",
  win: "#f6d77c",
  loss: "#f39b89",
  elixir: "#c44fd6",
  water: "#34dcc8",
  grass: "#a2bc41",
} as const;

export const gameFont = "system-ui, -apple-system, Segoe UI, Arial, sans-serif";
