import {
  Easing,
  Interactive,
  Sequence,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { Replay, Shot } from "./Replay";
import { CardPortrait, ElixirOrb, GameFrame, GameTag, PlayStrip, plays } from "./GameUI";
import { game, gameFont } from "./design";

const titleShadow = "0 5px 0 #09111f, 0 10px 22px #030811cc";

export const Opening = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <>
      <Shot
        name="Recorded model defeat"
        source="opus"
        camera="defense"
        start={8}
        speed={1}
        style={{ position: "absolute", inset: 0 }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "linear-gradient(90deg,#0e1420d9 0%,#0e14206b 43%,transparent 75%), linear-gradient(0deg,#0e1420ed,transparent 48%)",
        }}
      />
      <div style={{ position: "absolute", left: 90, top: 66 }}>
        <GameTag>ROYALEBENCH / CLASH ROYALE</GameTag>
      </div>
      <GameTag color={game.red} style={{ position: "absolute", right: 94, top: 66 }}>
        CLAUDE OPUS 5.5
      </GameTag>
      <Interactive.Div
        name="Benchmark identity"
        style={{
          position: "absolute",
          left: 92,
          top: 155,
          fontSize: 98,
          fontWeight: 1000,
          lineHeight: 0.96,
          letterSpacing: "-0.055em",
          textShadow: titleShadow,
          opacity: interpolate(frame, [1.85 * fps, 2.32 * fps], [1, 0], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      >
        RoyaleBench:<br />LLM Benchmark
      </Interactive.Div>
      <Interactive.Div
        name="Benchmark description"
        style={{
          position: "absolute",
          left: 98,
          top: 358,
          fontSize: 39,
          fontWeight: 700,
          color: game.win,
          textShadow: "0 3px 12px #030811",
          opacity: interpolate(frame, [1.85 * fps, 2.32 * fps], [1, 0], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      >
        Clash Royale decisions from fixed battle states.
      </Interactive.Div>
      <Sequence name="Defeat title" from={Math.round(2.35 * fps)} layout="none">
        <Interactive.Div
          name="Opening outcome"
          style={{
            position: "absolute",
            left: 92,
            bottom: 225,
            fontFamily: gameFont,
            fontSize: 164,
            fontWeight: 1000,
            lineHeight: 1,
            letterSpacing: "-0.05em",
            color: game.loss,
            textShadow: titleShadow,
            translate: interpolate(frame, [2.35 * fps, 2.72 * fps], ["0px 22px", "0px 0px"], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.16, 1, 0.3, 1),
            }),
          }}
        >
          DEFEAT.
        </Interactive.Div>
        <Interactive.Div
          name="Opening question"
          style={{
            position: "absolute",
            left: 101,
            bottom: 160,
            fontSize: 48,
            fontWeight: 750,
            color: game.win,
            textShadow: "0 3px 12px #030811",
          }}
        >
          Could the same cards have won?
        </Interactive.Div>
      </Sequence>
    </>
  );
};

export const Position = () => (
  <>
    <GameFrame
      style={{ position: "absolute", left: 88, top: 65, width: 520, height: 922 }}
    >
      <Replay source="opus" freeze={0} style={{ width: "100%", height: "100%" }} />
    </GameFrame>
    <div style={{ position: "absolute", left: 680, top: 68 }}>
      <GameTag color={game.gold}>ROYALEBENCH / ONE TASK</GameTag>
    </div>
    <Interactive.Div
      name="Benchmark task definition"
      style={{
        position: "absolute",
        left: 680,
        top: 141,
        fontSize: 76,
        fontWeight: 1000,
        letterSpacing: "-0.045em",
        lineHeight: 0.99,
        color: game.text,
        textShadow: titleShadow,
      }}
    >
      CARD CHOICE.<br />PLACEMENT. OUTCOME.
    </Interactive.Div>
    <div style={{ position: "absolute", left: 684, top: 303, fontSize: 33, color: game.muted }}>
      Each task starts from a fixed match state and a clear objective.
    </div>
    <div style={{ position: "absolute", left: 680, top: 374, display: "flex", gap: 18 }}>
      {[
        { label: "OVERTIME", value: "18s LEFT", color: game.gold },
        { label: "YOUR LEFT TOWER", value: "250 HP", color: game.blue },
        { label: "ENEMY LEFT TOWER", value: "450 HP", color: game.red },
      ].map(({ label, value, color }) => (
        <GameFrame
          key={label}
          accent={color}
          style={{ width: 331, height: 126, padding: "18px 19px" }}
        >
          <div style={{ fontSize: 20, fontWeight: 800, color, letterSpacing: "0.04em" }}>
            {label}
          </div>
          <div style={{ fontSize: 49, lineHeight: 1.22, fontWeight: 950 }}>{value}</div>
        </GameFrame>
      ))}
    </div>
    <Interactive.Div
      name="Task objective"
      style={{
        position: "absolute",
        left: 684,
        top: 524,
        fontSize: 43,
        fontWeight: 800,
        color: game.win,
      }}
    >
      Objective: win the tower race.
    </Interactive.Div>
    <GameFrame
      accent={game.elixir}
      style={{ position: "absolute", left: 680, top: 605, width: 1030, height: 270, padding: "23px 26px" }}
    >
      <div style={{ fontSize: 25, fontWeight: 850, color: game.elixir, letterSpacing: "0.06em" }}>
        HOW THE MODEL PLAYS
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 23 }}>
        {[
          { step: "01", label: "TEXT STATE", detail: "Towers, elixir, units", color: game.blue },
          { step: "02", label: "CARD + (X,Y)", detail: "cr play 0 3.5 11", color: game.elixir },
          { step: "03", label: "REPLAY GRADE", detail: "Objective checked", color: game.gold },
        ].map(({ step, label, detail, color }, index) => (
          <div key={step} style={{ display: "flex", alignItems: "center", gap: 10 }}>
            {index > 0 && <span style={{ fontSize: 35, color: game.win, fontWeight: 900 }}>→</span>}
            <div style={{ width: 286, minHeight: 131, border: `2px solid ${color}`, borderRadius: 9, padding: "14px 17px", background: game.surface }}>
              <div style={{ fontSize: 19, color, fontWeight: 900 }}>{step} / {label}</div>
              <div style={{ fontSize: 26, fontWeight: 800, marginTop: 15 }}>{detail}</div>
            </div>
          </div>
        ))}
      </div>
    </GameFrame>
    <div style={{ position: "absolute", left: 686, top: 899, fontSize: 27, color: game.muted }}>
      The model reads text; the arena is a replay for viewers.
    </div>
  </>
);

const timeLabel = (seconds: number) => `${seconds.toFixed(2)}s`;

export const SynchronizedAttempts = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const seconds = frame / fps;
  const active = Math.min(5, Math.floor(seconds / 2));
  const current = plays[active];
  return (
    <>
      <GameTag color={game.blue} style={{ position: "absolute", left: 78, top: 25 }}>
        MODEL / CLAUDE OPUS 5.5
      </GameTag>
      <GameTag color={game.gold} style={{ position: "absolute", right: 78, top: 25 }}>
        VALIDATED REFERENCE
      </GameTag>
      <GameFrame style={{ position: "absolute", left: 78, top: 80, width: 520, height: 914 }}>
        <Shot
          name="Synchronized model replay"
          source="opus"
          camera="full"
          start={0}
          speed={1}
          style={{ width: "100%", height: "100%" }}
        />
      </GameFrame>
      <GameFrame style={{ position: "absolute", right: 78, top: 80, width: 520, height: 914 }}>
        <Shot
          name="Synchronized reference replay"
          source="reference"
          camera="full"
          start={0}
          speed={1}
          style={{ width: "100%", height: "100%" }}
        />
      </GameFrame>
      <GameFrame
        accent={game.water}
        style={{ position: "absolute", left: 648, top: 80, width: 624, height: 914, padding: "29px 31px" }}
      >
        <div style={{ color: game.water, fontSize: 25, fontWeight: 850, letterSpacing: "0.05em" }}>
          MATCHED CONDITIONS
        </div>
        <Interactive.Div
          name="Matched plays title"
          style={{ fontSize: 76, fontWeight: 1000, lineHeight: 1.01, marginTop: 15, letterSpacing: "-0.04em" }}
        >
          SAME SIX PLAYS
        </Interactive.Div>
        <div style={{ display: "flex", gap: 13, marginTop: 22 }}>
          <GameTag color={game.blue} style={{ fontSize: 20, padding: "8px 10px" }}>ORDER ✓</GameTag>
          <GameTag color={game.blue} style={{ fontSize: 20, padding: "8px 10px" }}>TIMING ✓</GameTag>
          <GameTag color={game.elixir} style={{ fontSize: 20, padding: "8px 10px" }}>15 ELIXIR</GameTag>
        </div>
        <div style={{ marginTop: 28, borderTop: `2px solid ${game.line}`, paddingTop: 26 }}>
          <div style={{ color: game.muted, fontSize: 25, fontWeight: 700 }}>ALIGNED REPLAY</div>
          <div style={{ fontSize: 72, fontWeight: 950, fontVariantNumeric: "tabular-nums", lineHeight: 1.1 }}>
            {timeLabel(seconds)}
          </div>
        </div>
        <div style={{ display: "flex", gap: 23, alignItems: "center", marginTop: 25 }}>
          <CardPortrait card={current.card} width={112} />
          <div>
            <div style={{ fontSize: 23, fontWeight: 800, color: game.gold }}>
              PLAY {String(active + 1).padStart(2, "0")} / 06
            </div>
            <div style={{ fontSize: 48, fontWeight: 950, lineHeight: 1.13, margin: "6px 0 9px" }}>
              {current.label}
            </div>
            <ElixirOrb cost={current.cost} />
          </div>
        </div>
        <div style={{ marginTop: 26 }}><PlayStrip active={active} /></div>
        <div style={{ marginTop: 30, color: game.muted, fontSize: 28, lineHeight: 1.3 }}>
          {seconds < 10.3 ? "Only the card placements change." : "The same resources reach opposite outcomes."}
        </div>
      </GameFrame>
      <div
        style={{
          position: "absolute", left: 95, top: 88, zIndex: 4,
          background: "#0e1420dc", borderRadius: 6, padding: "7px 10px",
          fontSize: 25, fontWeight: 850, fontVariantNumeric: "tabular-nums",
        }}
      >
        {timeLabel(Math.min(10.35, seconds))}
      </div>
      <div
        style={{
          position: "absolute", right: 95, top: 88, zIndex: 4,
          background: "#0e1420dc", borderRadius: 6, padding: "7px 10px",
          fontSize: 25, fontWeight: 850, fontVariantNumeric: "tabular-nums",
        }}
      >
        {timeLabel(Math.min(11.2, seconds))}
      </div>
    </>
  );
};

const PlacementRing = ({ x, y, color }: { x: number; y: number; color: string }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const scale = interpolate(frame, [0, 0.28 * fps], [1.28, 1], { extrapolateRight: "clamp" });
  return (
    <div
      style={{
        position: "absolute", left: x - 72, top: y - 72, width: 144, height: 144,
        border: `7px dashed ${color}`, borderRadius: "50%", background: "#0e142018",
        boxShadow: `0 0 0 4px #0e1420, 0 0 23px ${color}`,
        scale,
        pointerEvents: "none",
      }}
    >
      <div style={{ position: "absolute", left: 59, top: 59, width: 13, height: 13, borderRadius: "50%", background: color }} />
    </div>
  );
};

const ComparisonFrame = ({
  leftCamera,
  rightCamera,
  freeze,
}: {
  leftCamera: "defense" | "attack";
  rightCamera: "defense" | "attack";
  freeze: number;
}) => (
  <>
    <GameFrame style={{ position: "absolute", left: 88, top: 303, width: 826, height: 526 }}>
      <Replay source="opus" camera={leftCamera} freeze={freeze} style={{ width: "100%", height: "100%" }} />
    </GameFrame>
    <GameFrame style={{ position: "absolute", right: 88, top: 303, width: 826, height: 526 }}>
      <Replay source="reference" camera={rightCamera} freeze={freeze} style={{ width: "100%", height: "100%" }} />
    </GameFrame>
    <GameTag color={game.red} style={{ position: "absolute", left: 88, top: 243 }}>
      MODEL ATTEMPT / LOSS
    </GameTag>
    <GameTag color={game.gold} style={{ position: "absolute", right: 88, top: 243 }}>
      VALIDATED REFERENCE / WIN
    </GameTag>
  </>
);

export const CannonDecision = () => (
  <>
    <div style={{ position: "absolute", left: 91, top: 61 }}><CardPortrait card="Cannon" width={95} /></div>
    <Interactive.Div
      name="Cannon contrast title"
      style={{ position: "absolute", left: 215, top: 65, fontSize: 76, fontWeight: 1000, letterSpacing: "-0.04em" }}
    >
      CANNON PLACEMENT
    </Interactive.Div>
    <GameTag color={game.water} style={{ position: "absolute", right: 89, top: 75 }}>
      MATCHED FREEZE / 3.00s
    </GameTag>
    <ComparisonFrame leftCamera="defense" rightCamera="defense" freeze={60} />
    <PlacementRing x={445} y={588} color={game.loss} />
    <PlacementRing x={1340} y={550} color={game.win} />
    <div style={{ position: "absolute", left: 910, top: 535, fontSize: 70, color: game.gold }}>➜</div>
    <div style={{ position: "absolute", left: 91, top: 854, fontSize: 45, fontWeight: 850, color: game.win }}>
      Reference: ½ tile left, 1 tile higher.
    </div>
    <div style={{ position: "absolute", right: 93, top: 863, fontSize: 25, color: game.muted }}>
      One visible difference in the full sequence
    </div>
  </>
);

export const LogDecision = () => (
  <>
    <div style={{ position: "absolute", left: 91, top: 61 }}><CardPortrait card="Log" width={95} /></div>
    <Interactive.Div
      name="Log contrast title"
      style={{ position: "absolute", left: 215, top: 65, fontSize: 76, fontWeight: 1000, letterSpacing: "-0.04em" }}
    >
      SAME LOG. DIFFERENT TARGET.
    </Interactive.Div>
    <GameTag color={game.water} style={{ position: "absolute", right: 89, top: 163 }}>
      MATCHED FREEZE / 9.00s
    </GameTag>
    <ComparisonFrame leftCamera="attack" rightCamera="defense" freeze={180} />
    <PlacementRing x={271} y={644} color={game.loss} />
    <PlacementRing x={1215} y={559} color={game.win} />
    <div style={{ position: "absolute", left: 910, top: 535, fontSize: 70, color: game.gold }}>➜</div>
    <div style={{ position: "absolute", left: 91, top: 853, fontSize: 40, fontWeight: 850, color: game.loss }}>
      Model: enemy tower
    </div>
    <div style={{ position: "absolute", right: 91, top: 853, fontSize: 40, fontWeight: 850, color: game.win }}>
      Reference: incoming Giant
    </div>
  </>
);

export const AgentInterface = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <>
      <GameTag color={game.elixir} style={{ position: "absolute", left: 90, top: 55 }}>
        THE AGENT INTERFACE
      </GameTag>
      <Interactive.Div
        name="Agent contract title"
        style={{ position: "absolute", left: 87, top: 128, fontSize: 90, fontWeight: 1000, letterSpacing: "-0.04em" }}
      >
        TEXT IN. PLACEMENT OUT.
      </Interactive.Div>
      <GameFrame
        accent={game.blue}
        style={{ position: "absolute", left: 90, top: 270, width: 925, height: 610, padding: "27px 31px" }}
      >
        <div style={{ fontSize: 25, fontWeight: 850, color: game.blue, letterSpacing: "0.05em" }}>
          OBSERVATION / SELECTED ACTUAL FIELDS
        </div>
        <div
          style={{
            marginTop: 33, fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
            fontSize: 36, lineHeight: 1.67, fontWeight: 650,
          }}
        >
          <div>TIME LEFT: 0:18 · OVERTIME</div>
          <div>YOUR ELIXIR: 7.0 / 10</div>
          <div>YOUR LEFT TOWER: 250 HP</div>
          <div>ENEMY: Giant at (3.5, 12.0)</div>
        </div>
        <div style={{ marginTop: 38, borderTop: `2px solid ${game.line}`, paddingTop: 21, fontSize: 29, color: game.muted }}>
          The simulation pauses while the model chooses.
        </div>
      </GameFrame>
      <GameFrame
        accent={game.elixir}
        style={{ position: "absolute", right: 90, top: 270, width: 735, height: 610, padding: "27px 30px" }}
      >
        <div style={{ fontSize: 25, fontWeight: 850, color: game.elixir, letterSpacing: "0.05em" }}>
          ACTION / FIRST RECORDED PLAY
        </div>
        <Interactive.Div
          name="Card coordinate command"
          style={{
            marginTop: 20, padding: "13px 20px", borderRadius: 9,
            background: game.background, border: `2px solid ${game.line}`,
            fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
            fontSize: 41, fontWeight: 750, color: game.win,
            opacity: interpolate(frame, [4.5 * fps, 5 * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
          }}
        >
          $ cr play 0 3.5 11
        </Interactive.Div>
        <div style={{ display: "flex", gap: 28, alignItems: "center", marginTop: 29 }}>
          <div style={{ width: 228, textAlign: "center" }}>
            <div style={{ width: "fit-content", margin: "0 auto" }}><CardPortrait card="IceSpirits" width={140} /></div>
            <div style={{ marginTop: 13, fontSize: 23, fontWeight: 850, color: game.elixir }}>SLOT 0</div>
            <div style={{ fontSize: 29, fontWeight: 800 }}>Ice Spirits</div>
          </div>
          <div style={{ fontSize: 54, color: game.gold }}>➜</div>
          <GameFrame accent={game.blue} style={{ width: 220, height: 350 }}>
            <Replay source="opus" freeze={0} style={{ width: "100%", height: "100%" }} />
          </GameFrame>
        </div>
        <div style={{ marginTop: 7, textAlign: "right", fontSize: 25, fontWeight: 800, color: game.blue }}>
          ARENA COORDINATES (3.5, 11)
        </div>
      </GameFrame>
    </>
  );
};

const ObjectiveMarks = () => (
  <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 11, marginTop: 24 }}>
    {Array.from({ length: 21 }, (_, index) => {
      const completed = index < 14;
      return (
        <div
          key={index}
          style={{
            height: 92, display: "grid", placeItems: "center",
            background: completed ? game.panel : "#412832",
            border: `2px solid ${completed ? game.gold : game.loss}`,
            borderRadius: 8, color: completed ? game.win : game.loss,
            fontSize: 48, fontWeight: 950,
          }}
        >
          {completed ? "✓" : "×"}
        </div>
      );
    })}
  </div>
);

export const RunResult = () => (
  <>
    <GameTag color={game.gold} style={{ position: "absolute", left: 91, top: 70 }}>
      ONE FULL RUN / ROYALEBENCH V9@1
    </GameTag>
    <Interactive.Div
      name="Run result title"
      style={{ position: "absolute", left: 88, top: 150, fontSize: 79, fontWeight: 1000, letterSpacing: "-0.04em" }}
    >
      CLAUDE OPUS 5.5
    </Interactive.Div>
    <GameFrame
      accent={game.gold}
      style={{ position: "absolute", left: 89, top: 292, width: 832, height: 553, padding: "31px 42px" }}
    >
      <div style={{ color: game.gold, fontSize: 27, fontWeight: 850 }}>TASK OBJECTIVE SUCCESS</div>
      <div style={{ fontSize: 250, fontWeight: 1000, lineHeight: 1.1, letterSpacing: "-0.07em", fontVariantNumeric: "tabular-nums" }}>
        <span style={{ color: game.win }}>14</span><span style={{ color: game.muted }}>/</span>21
      </div>
      <div style={{ fontSize: 40, fontWeight: 800 }}>objectives completed</div>
      <div style={{ marginTop: 14, fontSize: 27, color: game.muted }}>Includes objectives beyond match wins.</div>
    </GameFrame>
    <GameFrame
      accent={game.blue}
      style={{ position: "absolute", right: 89, top: 292, width: 830, height: 553, padding: "31px 33px" }}
    >
      <div style={{ fontSize: 27, fontWeight: 850, color: game.blue }}>21 TASK OBJECTIVES</div>
      <ObjectiveMarks />
      <div style={{ display: "flex", gap: 34, marginTop: 25, fontSize: 29, fontWeight: 750 }}>
        <span style={{ color: game.win }}>14 completed</span>
        <span style={{ color: game.loss }}>7 missed</span>
      </div>
      <div style={{ marginTop: 14, fontSize: 23, color: game.muted }}>Marks grouped by outcome.</div>
    </GameFrame>
    <div style={{ position: "absolute", left: 95, top: 884, color: game.muted, fontSize: 28 }}>
      One attempt per task · Valkyrie + Modal · independently replayed and verified
    </div>
  </>
);

export const Closing = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <>
      <Replay source="reference" camera="attack" start={8} style={{ position: "absolute", inset: 0 }} />
      <div style={{ position: "absolute", left: 90, top: 64 }}>
        <GameTag color={game.gold}>VALIDATED REFERENCE / WINNING CONNECTION / REPLAY</GameTag>
      </div>
      <div
        style={{
          position: "absolute", inset: 0, background: game.background,
          opacity: interpolate(frame, [3.3 * fps, 3.8 * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
        }}
      />
      <Sequence name="End card" from={Math.round(3.65 * fps)} layout="none">
        <svg
          width="164" height="125" viewBox="0 0 164 125"
          style={{ position: "absolute", left: 98, top: 260, filter: "drop-shadow(0 5px 0 #65471e)" }}
        >
          <path d="M12 31L38 64 82 10 126 64 152 31 145 97H19Z" fill={game.gold} stroke="#65471e" strokeWidth="8" strokeLinejoin="round" />
          <path d="M22 103H142V115H22Z" fill={game.win} stroke="#65471e" strokeWidth="6" />
        </svg>
        <Interactive.Div
          name="Project end title"
          style={{
            position: "absolute", left: 90, top: 394,
            fontSize: 161, fontWeight: 1000, letterSpacing: "-0.055em", lineHeight: 1,
            textShadow: titleShadow,
            translate: interpolate(frame, [3.65 * fps, 4.05 * fps], ["0px 20px", "0px 0px"], {
              extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(0.16, 1, 0.3, 1),
            }),
          }}
        >
          ROYALEBENCH
        </Interactive.Div>
        <Interactive.Div
          name="Closing line"
          style={{ position: "absolute", left: 99, top: 574, fontSize: 47, color: game.win, fontWeight: 750 }}
        >
          The right cards are only the beginning.
        </Interactive.Div>
        <Interactive.Div
          name="Repository URL"
          style={{ position: "absolute", left: 99, top: 724, fontSize: 38, color: game.water, fontWeight: 750 }}
        >
          github.com/ishanvepa/RoyaleBench
        </Interactive.Div>
        <div style={{ position: "absolute", left: 99, top: 815, fontSize: 25, color: game.muted }}>
          Built on RoyaleGym / RoyaleSim
        </div>
      </Sequence>
    </>
  );
};
