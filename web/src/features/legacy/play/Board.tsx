import type { BoardEntity, BoardSpell, BoardZone, PlayState } from "@/api/types";
import { BOARD_H, BOARD_W, TILE, boardSummary, bodyRadius, drawOrder, hpColor, hpFraction, isTower, sideOf, toPx } from "./geometry";
import type { BoardMarker } from "./moves";

// The arena is game artwork rather than interface chrome, so its greens, water and wood are literal colours in both themes.
const GRASS = "#8fc26a";
const GRASS_DARK = "#86b962";
const WATER = "#4aa3df";
const WOOD = "#b98b5a";
const CHECKER = "rb-board-checker";

function Arena() {
  const river = 15 * TILE;
  return (
    <g aria-hidden>
      <defs>
        <pattern id={CHECKER} width={2 * TILE} height={2 * TILE} patternUnits="userSpaceOnUse">
          <rect x={TILE} y={0} width={TILE} height={TILE} fill={GRASS_DARK} />
          <rect x={0} y={TILE} width={TILE} height={TILE} fill={GRASS_DARK} />
        </pattern>
      </defs>
      <rect width={BOARD_W} height={BOARD_H} fill={GRASS} />
      <rect width={BOARD_W} height={BOARD_H} fill={`url(#${CHECKER})`} />
      <rect width={BOARD_W} height={15 * TILE} style={{ fill: "var(--rb-side-red)" }} opacity={0.07} />
      <rect y={17 * TILE} width={BOARD_W} height={15 * TILE} style={{ fill: "var(--rb-side-blue)" }} opacity={0.07} />
      <rect y={river} width={BOARD_W} height={2 * TILE} fill={WATER} />
      {[2.5, 13.5].map((x) => (
        <rect key={x} x={x * TILE} y={river} width={2 * TILE} height={2 * TILE} fill={WOOD} />
      ))}
    </g>
  );
}

function Zone({ zone }: { zone: BoardZone }) {
  const [x, y] = toPx(zone.x, zone.y);
  return <circle cx={x} cy={y} r={4} fill="none" stroke="#fff" strokeOpacity={0.7} strokeDasharray="2 2" />;
}

function Spell({ spell }: { spell: BoardSpell }) {
  const [x, y] = toPx(spell.x, spell.y);
  const side = sideOf(spell.team);
  return (
    <g>
      <circle cx={x} cy={y} r={spell.radius * TILE} style={{ fill: side.fill, stroke: side.fill }} fillOpacity={0.18} strokeDasharray="4 3" />
      <text x={x} y={y - spell.radius * TILE - 3} fontSize={10} textAnchor="middle" fill="#1b1b1b">
        {spell.name}
      </text>
    </g>
  );
}

function Unit({ entity }: { entity: BoardEntity }) {
  const [x, y] = toPx(entity.x, entity.y);
  const r = bodyRadius(entity);
  const side = sideOf(entity.team);
  const fraction = hpFraction(entity.hp, entity.max_hp);
  const barWidth = Math.max(16, 2 * r);
  const opacity = entity.deploying ? 0.5 : 1;
  const solid = isTower(entity) || entity.kind === "building";
  return (
    // Drawn at the origin and moved with a CSS transform, so a unit that is still on the board next turn slides to its new place.
    <g style={{ transform: `translate(${x}px, ${y}px)` }} className="transition-transform duration-300 ease-out">
      {solid ? (
        <rect x={-r} y={-r} width={2 * r} height={2 * r} rx={3} strokeWidth={2} opacity={opacity} style={{ fill: side.fill, stroke: side.stroke }} />
      ) : (
        <>
          {entity.flying ? <ellipse cx={0} cy={r} rx={r} ry={r * 0.4} fill="#000" opacity={0.2} /> : null}
          <circle r={r} strokeWidth={entity.flying ? 2 : 1.5} opacity={opacity} style={{ fill: side.fill, stroke: entity.flying ? "#fff" : side.stroke }} />
        </>
      )}
      {r >= 6 ? (
        <text y={4} fontSize={Math.min(12, r)} fontWeight={600} textAnchor="middle" fill="#fff">
          {entity.label}
        </text>
      ) : null}
      <rect x={-barWidth / 2} y={-r - 7} width={barWidth} height={4} fill="#000" opacity={0.55} />
      <rect x={-barWidth / 2} y={-r - 7} width={barWidth * fraction} height={4} fill={hpColor(fraction)} />
      {isTower(entity) ? (
        <text y={-r - 10} fontSize={11} fontWeight={600} textAnchor="middle" fill="#1b1b1b">
          {entity.hp}
        </text>
      ) : null}
    </g>
  );
}

interface BoardProps {
  state: Pick<PlayState, "entities" | "spells" | "zones" | "opponent">;
  /** Places to highlight, such as every spot the hovered card could be played. */
  markers?: readonly BoardMarker[];
}

/** The arena, drawn from the server's snapshot. Nothing here is interactive: moves are chosen from the list beside it. */
export function Board({ state, markers = [] }: BoardProps) {
  return (
    <svg viewBox={`0 0 ${BOARD_W} ${BOARD_H}`} role="img" aria-label={boardSummary(state)} className="h-auto w-full rounded-lg border border-line" fontFamily="system-ui, sans-serif">
      <Arena />
      {state.zones.map((zone) => (
        <Zone key={zone.name} zone={zone} />
      ))}
      {state.spells.map((spell, i) => (
        <Spell key={`${spell.team}-${spell.name}-${i}`} spell={spell} />
      ))}
      {drawOrder(state.entities).map((entity) => (
        <Unit key={entity.id} entity={entity} />
      ))}
      {markers.map((marker) => {
        const [x, y] = toPx(marker.x, marker.y);
        return (
          <g key={marker.key} pointerEvents="none">
            <circle cx={x} cy={y} r={marker.active ? 8 : 5} strokeWidth={2} stroke="#fff" fillOpacity={marker.active ? 0.95 : 0.6} style={{ fill: "var(--rb-info)" }} />
          </g>
        );
      })}
    </svg>
  );
}
