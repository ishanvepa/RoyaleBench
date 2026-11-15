import {
  Interactive,
  Sequence,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { Badge, Clock, Marker, Replay, Shot } from "./Replay";
import { body, display, headline, ink, lime, orange, paper } from "./design";

const label = {
  fontFamily: body,
  fontSize: 38,
  fontWeight: 700,
  letterSpacing: "0.015em",
};

export const ColdOpen = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <>
      <Shot
        name="Opus final seconds close-up"
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
          background: "linear-gradient(0deg,rgba(0,0,0,0.80),transparent 65%)",
          pointerEvents: "none",
        }}
      />
      <Interactive.Div
        name="Model label"
        style={{
          ...label,
          position: "absolute",
          top: 90,
          left: 100,
          color: paper,
          background: ink,
          padding: "16px 24px",
        }}
      >
        CLAUDE OPUS 5.5
      </Interactive.Div>
      <Sequence from={Math.round(2.4 * fps)} layout="none" name="Loss reveal">
        <Interactive.Div
          name="Lost this title"
          style={{
            ...headline,
            fontSize: 180,
            position: "absolute",
            left: 100,
            bottom: 110,
            color: paper,
            translate: interpolate(
              frame,
              [2.4 * fps, 2.6 * fps],
              ["0px 20px", "0px 0px"],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
            ),
          }}
        >
          LOST THIS.
        </Interactive.Div>
      </Sequence>
      <div style={{ position: "absolute", right: 100, top: 110 }}>
        <Clock start={8} />
      </div>
    </>
  );
};

export const Setup = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <>
      <div
        style={{
          position: "absolute",
          left: 100,
          top: 60,
          width: 540,
          height: 960,
          rotate: "-2deg",
        }}
      >
        <Replay
          source="opus"
          freeze={0}
          style={{ width: "100%", height: "100%" }}
        />
      </div>
      <Interactive.Div
        name="Time remaining"
        style={{
          ...headline,
          position: "absolute",
          left: 790,
          top: 170,
          fontSize: 190,
          color: ink,
          translate: interpolate(
            frame,
            [0, 0.3 * fps],
            ["0px 36px", "0px 0px"],
            { extrapolateRight: "clamp" },
          ),
        }}
      >
        18 SECONDS.
      </Interactive.Div>
      <Interactive.Div
        name="Tower health"
        style={{
          ...headline,
          position: "absolute",
          left: 790,
          top: 365,
          fontSize: 230,
          color: orange,
        }}
      >
        250 HP.
      </Interactive.Div>
      <Interactive.Div
        name="Overtime condition"
        style={{
          position: "absolute",
          left: 800,
          top: 685,
          fontFamily: body,
          fontSize: 54,
          lineHeight: 1.2,
          color: ink,
          maxWidth: 950,
        }}
      >
        Next tower down wins.
      </Interactive.Div>
      <Interactive.Div
        name="Opponent tower health"
        style={{
          position: "absolute",
          left: 800,
          top: 815,
          fontFamily: body,
          fontSize: 38,
          color: ink,
        }}
      >
        Enemy tower: 450 HP
      </Interactive.Div>
      <Interactive.Div
        name="Opening frame source"
        style={{
          position: "absolute",
          left: 100,
          bottom: 28,
          fontFamily: body,
          fontSize: 25,
          color: ink,
        }}
      >
        Opening replay frame · first card deployment
      </Interactive.Div>
    </>
  );
};

export const Attempt = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const time = frame / fps;
  return (
    <>
      <Shot
        name="Opus full arena"
        source="opus"
        camera="full"
        start={0}
        speed={1}
        style={{
          position: "absolute",
          left: 75,
          top: 50,
          width: 540,
          height: 960,
        }}
      />
      <Shot
        name="Opus defense close-up"
        source="opus"
        camera="defense"
        start={0}
        speed={1}
        style={{
          position: "absolute",
          left: 690,
          top: 180,
          width: 1120,
          height: 700,
        }}
      />
      <Interactive.Div
        name="Attempt title"
        style={{
          ...label,
          position: "absolute",
          left: 690,
          top: 90,
          color: paper,
        }}
      >
        OPUS PLAYS IT OUT.
      </Interactive.Div>
      <div style={{ position: "absolute", left: 690, top: 910 }}>
        <Badge>
          {time < 2
            ? "Ice Spirits"
            : time < 4
              ? "Cannon"
              : time < 6
                ? "Fireball → tower"
                : time < 8
                  ? "Hog Rider"
                  : time < 10
                    ? "Log → tower"
                    : "Too late."}
        </Badge>
      </div>
      <div style={{ position: "absolute", right: 100, top: 95 }}>
        <Clock />
      </div>
      {time > 10.35 ? (
        <div
          style={{
            position: "absolute",
            right: 110,
            bottom: 100,
            background: orange,
            color: paper,
            padding: "15px 25px",
            fontFamily: display,
            fontSize: 64,
          }}
        >
          0–1. LOSS.
        </div>
      ) : null}
    </>
  );
};

export const Decision = () => (
  <>
    <Replay
      source="opus"
      camera="attack"
      freeze={160}
      style={{ position: "absolute", inset: 0 }}
    />
    <div
      style={{ position: "absolute", inset: 0, background: "rgba(0,0,0,.32)" }}
    />
    <Interactive.Div
      name="Freeze label"
      style={{
        ...label,
        position: "absolute",
        left: 100,
        top: 100,
        color: paper,
      }}
    >
      FREEZE AT THE FIFTH PLAY.
    </Interactive.Div>
    <Interactive.Div
      name="Log decision title"
      style={{
        ...headline,
        position: "absolute",
        left: 100,
        bottom: 210,
        color: paper,
        fontSize: 150,
      }}
    >
      LOG ON THE TOWER.
    </Interactive.Div>
    <Interactive.Div
      name="Unresolved Giant"
      style={{
        position: "absolute",
        left: 108,
        bottom: 110,
        color: paper,
        fontFamily: body,
        fontSize: 55,
      }}
    >
      The Giant is still coming.
    </Interactive.Div>
    <Marker x={375} y={445} width={350} height={240} color={lime} />
  </>
);

export const Reference = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const time = frame / fps;
  return (
    <>
      <Shot
        name="Reference full arena"
        source="reference"
        camera="full"
        start={0}
        speed={1}
        style={{
          position: "absolute",
          left: 75,
          top: 50,
          width: 540,
          height: 960,
        }}
      />
      <Shot
        name="Reference defense close-up"
        source="reference"
        camera="defense"
        start={0}
        speed={1}
        style={{
          position: "absolute",
          left: 690,
          top: 180,
          width: 1120,
          height: 700,
        }}
      />
      <Interactive.Div
        name="Reference label"
        style={{
          ...label,
          position: "absolute",
          left: 690,
          top: 90,
          color: lime,
        }}
      >
        VALIDATED REFERENCE
      </Interactive.Div>
      <div style={{ position: "absolute", left: 690, top: 910 }}>
        <Badge accent>
          {time < 2
            ? "Same Ice Spirits."
            : time < 4
              ? "Different Cannon placement."
              : time < 8
                ? "Same Fireball. Same Hog."
                : time < 10
                  ? "Log → Giant"
                  : "Tower stays up."}
        </Badge>
      </div>
      <div style={{ position: "absolute", right: 100, top: 95 }}>
        <Clock source="reference" />
      </div>
      {time > 11.2 ? (
        <div
          style={{
            position: "absolute",
            right: 110,
            bottom: 90,
            color: lime,
            fontFamily: display,
            fontSize: 64,
          }}
        >
          1–0. WIN.
        </div>
      ) : null}
    </>
  );
};

export const Placements = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const first = frame < 5 * fps;
  return (
    <>
      <Interactive.Div
        name="Same cards headline"
        style={{
          ...headline,
          fontSize: 132,
          position: "absolute",
          left: 100,
          top: 90,
          color: ink,
        }}
      >
        SAME CARDS. SAME ORDER.
      </Interactive.Div>
      <div
        style={{
          position: "absolute",
          left: 100,
          top: 320,
          width: 820,
          height: 550,
        }}
      >
        <Replay
          source="opus"
          camera={first ? "defense" : "attack"}
          freeze={first ? 60 : 180}
          style={{ width: "100%", height: "100%" }}
        />
      </div>
      <div
        style={{
          position: "absolute",
          left: 1000,
          top: 320,
          width: 820,
          height: 550,
        }}
      >
        <Replay
          source="reference"
          camera="defense"
          freeze={first ? 60 : 180}
          style={{ width: "100%", height: "100%" }}
        />
      </div>
      <Interactive.Div
        name="Opus comparison label"
        style={{
          ...label,
          position: "absolute",
          left: 100,
          top: 255,
          color: orange,
        }}
      >
        OPUS
      </Interactive.Div>
      <Interactive.Div
        name="Reference comparison label"
        style={{
          ...label,
          position: "absolute",
          left: 1000,
          top: 255,
          color: ink,
        }}
      >
        REFERENCE
      </Interactive.Div>
      <Interactive.Div
        name="Placement explanation"
        style={{
          fontFamily: body,
          fontSize: 54,
          fontWeight: 700,
          position: "absolute",
          left: 100,
          bottom: 95,
          color: ink,
        }}
      >
        {first
          ? "The Cannon pulls from a different spot."
          : "The reference spends Log on defense."}
      </Interactive.Div>
      {first ? (
        <>
          <Marker x={445} y={580} width={140} height={110} />
          <Marker x={1317} y={530} width={140} height={110} />
        </>
      ) : null}
      <Interactive.Div
        name="Comparison elixir"
        style={{
          position: "absolute",
          right: 100,
          bottom: 100,
          fontFamily: body,
          fontSize: 34,
          color: ink,
        }}
      >
        15 elixir each
      </Interactive.Div>
    </>
  );
};

export const Method = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <>
      <Interactive.Div
        name="Benchmark name"
        style={{
          ...headline,
          position: "absolute",
          left: 100,
          top: 100,
          fontSize: 150,
          color: paper,
        }}
      >
        ROYALEBENCH
      </Interactive.Div>
      <Interactive.Div
        name="Text interface explanation"
        style={{
          position: "absolute",
          left: 108,
          top: 300,
          fontFamily: body,
          fontSize: 60,
          color: lime,
        }}
      >
        The model gets text.
      </Interactive.Div>
      <Interactive.Pre
        name="Selected actual observation"
        style={{
          position: "absolute",
          left: 108,
          top: 415,
          fontFamily: "monospace",
          fontSize: 46,
          lineHeight: 1.45,
          color: paper,
          margin: 0,
        }}
      >{`TIME LEFT: 0:18 · OVERTIME\nYOUR ELIXIR: 7.0 / 10\nYOUR LEFT TOWER: 250 HP\nENEMY: Giant at (3.5, 12.0)`}</Interactive.Pre>
      <Sequence name="Actual command reveal" from={3 * fps} layout="none">
        <Interactive.Div
          name="Coordinate command"
          style={{
            position: "absolute",
            left: 108,
            top: 775,
            fontFamily: "monospace",
            fontSize: 72,
            color: lime,
            opacity: interpolate(frame, [3 * fps, 3.2 * fps], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        >
          $ cr play 0 3.5 11
        </Interactive.Div>
      </Sequence>
      <Interactive.Div
        name="Thinking pauses game"
        style={{
          position: "absolute",
          left: 108,
          bottom: 95,
          fontFamily: body,
          fontSize: 39,
          color: paper,
        }}
      >
        Choose a card + coordinates. The game pauses while it thinks.
      </Interactive.Div>
    </>
  );
};

export const Results = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <>
      <Interactive.Div
        name="Result cohort"
        style={{
          ...label,
          position: "absolute",
          left: 100,
          top: 100,
          color: ink,
        }}
      >
        OPUS 5.5 · ROYALEBENCH V6
      </Interactive.Div>
      <Interactive.Div
        name="Objectives completed"
        style={{
          ...headline,
          position: "absolute",
          left: 85,
          top: 230,
          fontSize: 350,
          color: ink,
        }}
      >
        10/14
      </Interactive.Div>
      <Interactive.Div
        name="Score meaning"
        style={{
          position: "absolute",
          left: 108,
          top: 640,
          fontFamily: body,
          fontSize: 62,
          color: ink,
        }}
      >
        objectives completed.
      </Interactive.Div>
      <Interactive.Div
        name="Single run qualification"
        style={{
          position: "absolute",
          left: 108,
          bottom: 160,
          fontFamily: body,
          fontSize: 36,
          color: ink,
        }}
      >
        One run. One attempt per task. v6@1.
      </Interactive.Div>
      <Interactive.Div
        name="Infrastructure"
        style={{
          position: "absolute",
          left: 108,
          bottom: 90,
          fontFamily: body,
          fontSize: 36,
          color: ink,
        }}
      >
        Valkyrie + Modal · independently replayed and verified
      </Interactive.Div>
      <div
        style={{
          position: "absolute",
          left: 1350,
          top: 220,
          width: 350,
          display: "grid",
          gridTemplateColumns: "repeat(2, 1fr)",
          gap: 20,
        }}
      >
        {Array.from({ length: 14 }, (_, i) => (
          <div
            key={i}
            style={{
              height: 55,
              background: i < 10 ? ink : orange,
              opacity: interpolate(frame, [i * 2, i * 2 + 4], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              }),
            }}
          />
        ))}
      </div>
      <Sequence from={5 * fps} layout="none" name="Result definition">
        <Interactive.Div
          name="Objective qualification"
          style={{
            position: "absolute",
            left: 108,
            top: 740,
            fontFamily: body,
            fontSize: 33,
            color: orange,
          }}
        >
          Task success rate — includes objectives beyond match wins.
        </Interactive.Div>
      </Sequence>
    </>
  );
};

export const Ending = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <>
      <Replay
        source="reference"
        camera="attack"
        start={8}
        style={{ position: "absolute", inset: 0 }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: ink,
          opacity: interpolate(frame, [3.1 * fps, 3.6 * fps], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      />
      <Sequence from={Math.round(3.3 * fps)} layout="none" name="Final title">
        <Interactive.Div
          name="Project end card"
          style={{
            ...headline,
            fontSize: 220,
            position: "absolute",
            left: 100,
            top: 300,
            color: paper,
          }}
        >
          ROYALEBENCH
        </Interactive.Div>
        <Interactive.Div
          name="Repository URL"
          style={{
            fontFamily: body,
            fontSize: 48,
            position: "absolute",
            left: 110,
            top: 600,
            color: lime,
          }}
        >
          github.com/ishanvepa/RoyaleBench
        </Interactive.Div>
        <Interactive.Div
          name="Engine credit"
          style={{
            fontFamily: body,
            fontSize: 30,
            position: "absolute",
            left: 110,
            bottom: 110,
            color: paper,
          }}
        >
          Built on RoyaleGym / RoyaleSim
        </Interactive.Div>
      </Sequence>
    </>
  );
};
