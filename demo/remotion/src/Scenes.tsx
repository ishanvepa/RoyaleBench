import {
  Easing,
  Interactive,
  Sequence,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { Clock, Marker, Replay, Shot } from "./Replay";
import { ActionRail } from "./ActionRail";
import { body, ink, orange, paper } from "./design";

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
          background: "linear-gradient(0deg,rgba(0,0,0,.84),transparent 70%)",
          pointerEvents: "none",
        }}
      />
      <Interactive.Div
        name="Opening identity"
        style={{
          position: "absolute",
          left: 100,
          top: 76,
          fontFamily: "Arial, sans-serif",
          fontSize: 29,
          fontWeight: 700,
          letterSpacing: "0.09em",
          color: "#f3efe5",
          background: "#191b17",
          padding: "14px 20px",
          borderLeft: "5px solid #d0ed58",
        }}
      >
        ROYALEBENCH / CLAUDE OPUS 5.5
      </Interactive.Div>
      <div style={{ position: "absolute", right: 100, top: 95 }}>
        <Clock start={8} />
      </div>
      <Sequence from={Math.round(2.4 * fps)} layout="none" name="Loss reveal">
        <Interactive.Div
          name="Lost this title"
          style={{
            position: "absolute",
            left: 100,
            bottom: 164,
            fontFamily: "ReplayDisplay, Impact, sans-serif",
            lineHeight: 0.96,
            fontSize: 190,
            letterSpacing: "-0.025em",
            color: "#f3efe5",
            translate: interpolate(
              frame,
              [2.4 * fps, 2.7 * fps],
              ["0px 22px", "0px 0px"],
              {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
                easing: Easing.bezier(0.16, 1, 0.3, 1),
              },
            ),
            opacity: interpolate(frame, [2.4 * fps, 2.6 * fps], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        >
          LOST THIS.
        </Interactive.Div>
        <Interactive.Div
          name="Opening question"
          style={{
            position: "absolute",
            left: 108,
            bottom: 88,
            fontFamily: "Arial, sans-serif",
            fontSize: 42,
            color: "#d0ed58",
          }}
        >
          Could the same cards have won?
        </Interactive.Div>
      </Sequence>
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
          boxShadow: "0 16px 40px #191b1720",
        }}
      >
        <Replay
          source="opus"
          freeze={0}
          style={{ width: "100%", height: "100%" }}
        />
      </div>
      <Interactive.Div
        name="Benchmark premise"
        style={{
          position: "absolute",
          left: 790,
          top: 100,
          fontFamily: "Arial, sans-serif",
          fontSize: 32,
          fontWeight: 700,
          letterSpacing: "0.045em",
          color: "#191b17",
        }}
      >
        A CLASH ROYALE BENCHMARK FOR LLMS
      </Interactive.Div>
      <Interactive.Div
        name="Time remaining"
        style={{
          position: "absolute",
          left: 782,
          top: 214,
          fontFamily: "ReplayDisplay, Impact, sans-serif",
          fontSize: 182,
          lineHeight: 0.96,
          letterSpacing: "-0.025em",
          color: "#191b17",
          translate: interpolate(
            frame,
            [0, 0.4 * fps],
            ["0px 24px", "0px 0px"],
            {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.16, 1, 0.3, 1),
            },
          ),
        }}
      >
        18 SECONDS.
      </Interactive.Div>
      <Interactive.Div
        name="Tower health"
        style={{
          position: "absolute",
          left: 782,
          top: 415,
          fontFamily: "ReplayDisplay, Impact, sans-serif",
          fontSize: 225,
          lineHeight: 0.96,
          letterSpacing: "-0.025em",
          color: "#ec4a2e",
          opacity: interpolate(frame, [0.3 * fps, 0.6 * fps], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
          translate: interpolate(
            frame,
            [0.3 * fps, 0.7 * fps],
            ["0px 18px", "0px 0px"],
            {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.16, 1, 0.3, 1),
            },
          ),
        }}
      >
        250 HP.
      </Interactive.Div>
      <Interactive.Div
        name="Overtime condition"
        style={{
          position: "absolute",
          left: 790,
          top: 705,
          fontFamily: "Arial, sans-serif",
          fontSize: 54,
          lineHeight: 1.2,
          color: "#191b17",
        }}
      >
        Next tower down wins.
      </Interactive.Div>
      <div
        style={{
          position: "absolute",
          left: 790,
          right: 110,
          top: 815,
          borderTop: "2px solid #191b1726",
        }}
      />
      <Interactive.Div
        name="Opponent tower health"
        style={{
          position: "absolute",
          left: 790,
          top: 856,
          fontFamily: "Arial, sans-serif",
          fontSize: 38,
          color: "#191b17",
        }}
      >
        Enemy tower: 450 HP
      </Interactive.Div>
      <Interactive.Div
        name="Opening frame source"
        style={{
          position: "absolute",
          left: 100,
          bottom: 24,
          fontFamily: "Arial, sans-serif",
          fontSize: 23,
          color: "#191b17",
        }}
      >
        Opening replay frame · first deployment
      </Interactive.Div>
    </>
  );
};

export const Attempt = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
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
          top: 210,
          width: 1120,
          height: 650,
        }}
      />
      <Interactive.Div
        name="Attempt chapter"
        style={{
          position: "absolute",
          left: 690,
          top: 60,
          fontFamily: "Arial, sans-serif",
          fontSize: 27,
          fontWeight: 700,
          letterSpacing: "0.07em",
          color: "#ec4a2e",
        }}
      >
        01 / MODEL ATTEMPT
      </Interactive.Div>
      <Interactive.Div
        name="Attempt title"
        style={{
          position: "absolute",
          left: 686,
          top: 112,
          fontFamily: "ReplayDisplay, Impact, sans-serif",
          fontSize: 72,
          lineHeight: 1,
          color: "#f3efe5",
        }}
      >
        CLAUDE OPUS 5.5
      </Interactive.Div>
      <div style={{ position: "absolute", right: 110, top: 65 }}>
        <Clock />
      </div>
      <ActionRail />
      <Sequence name="Opus result" from={Math.ceil(10.35 * fps)} layout="none">
        <Interactive.Div
          name="Loss outcome"
          style={{
            position: "absolute",
            right: 135,
            top: 740,
            background: "#ec4a2e",
            color: "#f3efe5",
            padding: "14px 24px",
            fontFamily: "ReplayDisplay, Impact, sans-serif",
            fontSize: 58,
            translate: interpolate(
              frame,
              [10.35 * fps, 10.65 * fps],
              ["0px 16px", "0px 0px"],
              {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
                easing: Easing.bezier(0.16, 1, 0.3, 1),
              },
            ),
          }}
        >
          0–1 / LOSS
        </Interactive.Div>
      </Sequence>
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
      style={{
        position: "absolute",
        inset: 0,
        background: "linear-gradient(0deg,rgba(0,0,0,.85),rgba(0,0,0,.14) 80%)",
      }}
    />
    <Interactive.Div
      name="Freeze label"
      style={{
        position: "absolute",
        left: 100,
        top: 90,
        fontFamily: "Arial, sans-serif",
        fontSize: 30,
        fontWeight: 700,
        color: "#f3efe5",
        background: "#191b17",
        padding: "14px 20px",
        borderLeft: "5px solid #ec4a2e",
      }}
    >
      FREEZE / PLAY 05 / REPLAY 8.00s
    </Interactive.Div>
    <Marker x={375} y={445} width={350} height={240} color={orange} />
    <Interactive.Div
      name="Log decision title"
      style={{
        position: "absolute",
        left: 100,
        bottom: 212,
        fontFamily: "ReplayDisplay, Impact, sans-serif",
        fontSize: 145,
        letterSpacing: "-0.025em",
        lineHeight: 0.96,
        color: "#f3efe5",
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
        fontFamily: "Arial, sans-serif",
        fontSize: 52,
        color: "#f3efe5",
      }}
    >
      The Giant is still coming.
    </Interactive.Div>
  </>
);

export const Reference = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
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
      <Sequence
        name="Reference defense"
        durationInFrames={10 * fps}
        layout="none"
      >
        <Shot
          name="Reference defense close-up"
          source="reference"
          camera="defense"
          start={0}
          speed={1}
          style={{
            position: "absolute",
            left: 690,
            top: 210,
            width: 1120,
            height: 650,
          }}
        />
      </Sequence>
      <Sequence
        name="Cut to the winning connection"
        from={10 * fps}
        layout="none"
      >
        <Shot
          name="Reference attack close-up"
          source="reference"
          camera="attack"
          start={10}
          speed={1}
          style={{
            position: "absolute",
            left: 690,
            top: 210,
            width: 1120,
            height: 650,
          }}
        />
      </Sequence>
      <Interactive.Div
        name="Reference chapter"
        style={{
          position: "absolute",
          left: 690,
          top: 60,
          fontFamily: "Arial, sans-serif",
          fontSize: 27,
          fontWeight: 700,
          letterSpacing: "0.07em",
          color: "#d0ed58",
        }}
      >
        02 / SAME STARTING POSITION
      </Interactive.Div>
      <Interactive.Div
        name="Reference label"
        style={{
          position: "absolute",
          left: 686,
          top: 112,
          fontFamily: "ReplayDisplay, Impact, sans-serif",
          fontSize: 72,
          lineHeight: 1,
          color: "#f3efe5",
        }}
      >
        VALIDATED REFERENCE
      </Interactive.Div>
      <div style={{ position: "absolute", right: 110, top: 65 }}>
        <Clock source="reference" />
      </div>
      <ActionRail reference />
      <Sequence
        name="Reference result"
        from={Math.ceil(11.2 * fps)}
        layout="none"
      >
        <Interactive.Div
          name="Winning outcome"
          style={{
            position: "absolute",
            right: 135,
            top: 740,
            background: "#d0ed58",
            color: "#191b17",
            padding: "14px 24px",
            fontFamily: "ReplayDisplay, Impact, sans-serif",
            fontSize: 58,
            translate: interpolate(
              frame,
              [11.2 * fps, 11.5 * fps],
              ["0px 16px", "0px 0px"],
              {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
                easing: Easing.bezier(0.16, 1, 0.3, 1),
              },
            ),
          }}
        >
          1–0 / WIN
        </Interactive.Div>
      </Sequence>
    </>
  );
};

// Each comparison has its own clock, so annotations redraw on the second cut.
const CannonComparison = () => (
  <>
    <Replay
      source="opus"
      camera="defense"
      freeze={60}
      style={{
        position: "absolute",
        left: 100,
        top: 355,
        width: 820,
        height: 500,
      }}
    />
    <Replay
      source="reference"
      camera="defense"
      freeze={60}
      style={{
        position: "absolute",
        left: 1000,
        top: 355,
        width: 820,
        height: 500,
      }}
    />
    <Marker x={445} y={585} width={130} height={100} color={orange} />
    <Marker x={1335} y={550} width={130} height={100} color={ink} />
    <Interactive.Div
      name="Cannon comparison detail"
      style={{
        position: "absolute",
        left: 100,
        top: 902,
        fontFamily: "Arial, sans-serif",
        fontSize: 43,
        fontWeight: 700,
        color: "#191b17",
      }}
    >
      01 / A different Cannon placement.
    </Interactive.Div>
    <Interactive.Div
      name="Cannon freeze time"
      style={{
        position: "absolute",
        right: 100,
        top: 910,
        fontFamily: "Arial, sans-serif",
        fontSize: 27,
        color: "#191b17",
      }}
    >
      FREEZE / 3.00s
    </Interactive.Div>
  </>
);

const LogComparison = () => (
  <>
    <Replay
      source="opus"
      camera="attack"
      freeze={180}
      style={{
        position: "absolute",
        left: 100,
        top: 355,
        width: 820,
        height: 500,
      }}
    />
    <Replay
      source="reference"
      camera="defense"
      freeze={180}
      style={{
        position: "absolute",
        left: 1000,
        top: 355,
        width: 820,
        height: 500,
      }}
    />
    <Marker x={264} y={640} width={200} height={225} color={orange} />
    <Marker x={1215} y={550} width={185} height={145} color={ink} />
    <Interactive.Div
      name="Log comparison detail"
      style={{
        position: "absolute",
        left: 100,
        top: 902,
        fontFamily: "Arial, sans-serif",
        fontSize: 43,
        fontWeight: 700,
        color: "#191b17",
      }}
    >
      02 / Log on offense. Log on defense.
    </Interactive.Div>
    <Interactive.Div
      name="Log freeze time"
      style={{
        position: "absolute",
        right: 100,
        top: 910,
        fontFamily: "Arial, sans-serif",
        fontSize: 27,
        color: "#191b17",
      }}
    >
      FREEZE / 9.00s
    </Interactive.Div>
  </>
);

export const Placements = () => {
  const { fps } = useVideoConfig();
  return (
    <>
      <Interactive.Div
        name="Comparison headline"
        style={{
          position: "absolute",
          left: 95,
          top: 80,
          fontFamily: "ReplayDisplay, Impact, sans-serif",
          fontSize: 113,
          lineHeight: 0.96,
          letterSpacing: "-0.025em",
          color: "#191b17",
        }}
      >
        SAME CARDS. OPPOSITE RESULT.
      </Interactive.Div>
      <Interactive.Div
        name="Matched resources"
        style={{
          position: "absolute",
          left: 100,
          top: 222,
          fontFamily: "Arial, sans-serif",
          fontSize: 35,
          color: "#191b17",
        }}
      >
        Six plays. Same order. 15 elixir each.
      </Interactive.Div>
      <Interactive.Div
        name="Opus comparison label"
        style={{
          position: "absolute",
          left: 100,
          top: 300,
          fontFamily: "Arial, sans-serif",
          fontSize: 31,
          fontWeight: 700,
          letterSpacing: "0.025em",
          color: "#ec4a2e",
        }}
      >
        CLAUDE OPUS 5.5 / LOSS
      </Interactive.Div>
      <Interactive.Div
        name="Reference comparison label"
        style={{
          position: "absolute",
          left: 1000,
          top: 300,
          fontFamily: "Arial, sans-serif",
          fontSize: 31,
          fontWeight: 700,
          letterSpacing: "0.025em",
          color: "#191b17",
        }}
      >
        VALIDATED REFERENCE / WIN
      </Interactive.Div>
      <Sequence
        name="Compare Cannon placements"
        durationInFrames={5 * fps}
        layout="none"
      >
        <CannonComparison />
      </Sequence>
      <Sequence
        name="Compare Log targets"
        from={5 * fps}
        durationInFrames={5 * fps}
        layout="none"
      >
        <LogComparison />
      </Sequence>
      <Interactive.Div
        name="Comparison interpretation"
        style={{
          position: "absolute",
          left: 100,
          bottom: 45,
          fontFamily: "Arial, sans-serif",
          fontSize: 26,
          color: "#55584d",
        }}
      >
        Identical deployment times; placements vary across the full sequence.
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
        name="Interface chapter"
        style={{
          position: "absolute",
          left: 100,
          top: 80,
          fontFamily: "Arial, sans-serif",
          fontSize: 29,
          fontWeight: 700,
          letterSpacing: "0.06em",
          color: "#d0ed58",
        }}
      >
        THE AGENT INTERFACE
      </Interactive.Div>
      <Interactive.Div
        name="Text interface explanation"
        style={{
          position: "absolute",
          left: 95,
          top: 155,
          fontFamily: "ReplayDisplay, Impact, sans-serif",
          fontSize: 132,
          lineHeight: 0.96,
          letterSpacing: "-0.025em",
          color: "#f3efe5",
        }}
      >
        READ THE STATE. PICK A PLAY.
      </Interactive.Div>
      <div
        style={{
          position: "absolute",
          left: 100,
          top: 350,
          width: 1720,
          height: 510,
          border: "2px solid #45473e",
          background: "#22251f",
        }}
      />
      <Interactive.Div
        name="Observation source label"
        style={{
          position: "absolute",
          left: 140,
          top: 382,
          fontFamily: "Arial, sans-serif",
          fontSize: 25,
          fontWeight: 700,
          letterSpacing: "0.07em",
          color: "#afb2a3",
        }}
      >
        TEXT OBSERVATION / SELECTED ACTUAL FIELDS
      </Interactive.Div>
      <Interactive.Pre
        name="Selected actual observation"
        style={{
          position: "absolute",
          left: 140,
          top: 450,
          fontFamily: "monospace",
          fontSize: 42,
          lineHeight: 1.45,
          color: "#f3efe5",
          margin: 0,
        }}
      >{`TIME LEFT: 0:18 · OVERTIME\nYOUR ELIXIR: 7.0 / 10\nYOUR LEFT TOWER: 250 HP\nENEMY: Giant at (3.5, 12.0)`}</Interactive.Pre>
      <Sequence name="Actual command reveal" from={3 * fps} layout="none">
        <Interactive.Div
          name="Coordinate command"
          style={{
            position: "absolute",
            left: 140,
            top: 740,
            fontFamily: "monospace",
            fontSize: 59,
            color: "#d0ed58",
            opacity: interpolate(frame, [3 * fps, 3.3 * fps], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
            translate: interpolate(
              frame,
              [3 * fps, 3.4 * fps],
              ["0px 12px", "0px 0px"],
              {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
                easing: Easing.bezier(0.16, 1, 0.3, 1),
              },
            ),
          }}
        >
          $ cr play 0 3.5 11
        </Interactive.Div>
        <Interactive.Div
          name="Command explanation"
          style={{
            position: "absolute",
            right: 150,
            top: 765,
            fontFamily: "Arial, sans-serif",
            fontSize: 28,
            color: "#afb2a3",
          }}
        >
          card slot + arena coordinates
        </Interactive.Div>
      </Sequence>
      <Interactive.Div
        name="Thinking pauses game"
        style={{
          position: "absolute",
          left: 108,
          bottom: 102,
          fontFamily: "Arial, sans-serif",
          fontSize: 35,
          color: "#f3efe5",
        }}
      >
        The model gets text. The simulation pauses while it thinks.
      </Interactive.Div>
    </>
  );
};

const TaskMarks = () => {
  const frame = useCurrentFrame();
  return (
    <div style={{ position: "absolute", left: 1190, top: 300, width: 620 }}>
      <div
        style={{
          color: ink,
          fontFamily: body,
          fontSize: 28,
          fontWeight: 700,
          marginBottom: 25,
        }}
      >
        14 TASK OBJECTIVES
      </div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(7, 1fr)",
          gap: 12,
        }}
      >
        {Array.from({ length: 14 }, (_, i) => (
          <div
            key={i}
            style={{
              height: 100,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontFamily: body,
              fontWeight: 700,
              fontSize: 38,
              background: i < 10 ? ink : orange,
              color: paper,
              opacity: interpolate(frame, [8 + i * 2, 15 + i * 2], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              }),
            }}
          >
            {i < 10 ? "✓" : "×"}
          </div>
        ))}
      </div>
      <div
        style={{
          display: "flex",
          gap: 36,
          marginTop: 26,
          color: ink,
          fontFamily: body,
          fontSize: 29,
        }}
      >
        <span>10 completed</span>
        <span style={{ color: orange }}>4 missed</span>
      </div>
      <div
        style={{
          marginTop: 28,
          color: "#55584d",
          fontFamily: body,
          fontSize: 25,
          lineHeight: 1.4,
        }}
      >
        Grouped by outcome.
      </div>
    </div>
  );
};

export const Results = () => (
  <>
    <Interactive.Div
      name="Result cohort"
      style={{
        position: "absolute",
        left: 100,
        top: 90,
        fontFamily: "Arial, sans-serif",
        fontSize: 32,
        fontWeight: 700,
        letterSpacing: "0.035em",
        color: "#191b17",
      }}
    >
      CLAUDE OPUS 5.5 / ROYALEBENCH V6
    </Interactive.Div>
    <Interactive.Div
      name="Objectives completed"
      style={{
        position: "absolute",
        left: 85,
        top: 240,
        fontFamily: "ReplayDisplay, Impact, sans-serif",
        fontSize: 340,
        lineHeight: 0.96,
        letterSpacing: "-0.025em",
        color: "#191b17",
      }}
    >
      10/14
    </Interactive.Div>
    <Interactive.Div
      name="Score meaning"
      style={{
        position: "absolute",
        left: 105,
        top: 610,
        fontFamily: "Arial, sans-serif",
        fontSize: 58,
        color: "#191b17",
      }}
    >
      task objectives completed.
    </Interactive.Div>
    <Interactive.Div
      name="Objective qualification"
      style={{
        position: "absolute",
        left: 108,
        top: 708,
        fontFamily: "Arial, sans-serif",
        fontSize: 31,
        color: "#55584d",
      }}
    >
      Includes objectives beyond match wins.
    </Interactive.Div>
    <TaskMarks />
    <div
      style={{
        position: "absolute",
        left: 100,
        right: 100,
        top: 845,
        borderTop: "2px solid #191b1726",
      }}
    />
    <Interactive.Div
      name="Single run qualification"
      style={{
        position: "absolute",
        left: 108,
        top: 890,
        fontFamily: "Arial, sans-serif",
        fontSize: 32,
        color: "#191b17",
      }}
    >
      One run · one attempt per task · v6@1
    </Interactive.Div>
    <Interactive.Div
      name="Infrastructure"
      style={{
        position: "absolute",
        left: 108,
        top: 958,
        fontFamily: "Arial, sans-serif",
        fontSize: 30,
        color: "#55584d",
      }}
    >
      Valkyrie + Modal · independently replayed and verified
    </Interactive.Div>
  </>
);

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
      <Interactive.Div
        name="Repeated footage label"
        style={{
          position: "absolute",
          left: 100,
          top: 80,
          fontFamily: "Arial, sans-serif",
          fontSize: 29,
          fontWeight: 700,
          color: "#f3efe5",
          background: "#191b17",
          padding: "14px 20px",
        }}
      >
        REFERENCE / WINNING CONNECTION / REPLAY
      </Interactive.Div>
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: ink,
          opacity: interpolate(frame, [3.3 * fps, 3.7 * fps], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      />
      <Sequence from={Math.round(3.5 * fps)} layout="none" name="Final title">
        <Interactive.Div
          name="End card accent"
          style={{
            position: "absolute",
            left: 108,
            top: 265,
            width: 80,
            height: 7,
            background: "#d0ed58",
            scale: interpolate(frame, [3.5 * fps, 4.1 * fps], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.16, 1, 0.3, 1),
              output: "perceptual-scale",
            }),
            transformOrigin: "left center",
          }}
        />
        <Interactive.Div
          name="Project end card"
          style={{
            position: "absolute",
            left: 95,
            top: 325,
            fontFamily: "ReplayDisplay, Impact, sans-serif",
            fontSize: 210,
            lineHeight: 0.96,
            letterSpacing: "-0.025em",
            color: "#f3efe5",
            translate: interpolate(
              frame,
              [3.5 * fps, 4 * fps],
              ["0px 20px", "0px 0px"],
              {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
                easing: Easing.bezier(0.16, 1, 0.3, 1),
              },
            ),
            opacity: interpolate(frame, [3.5 * fps, 3.8 * fps], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        >
          ROYALEBENCH
        </Interactive.Div>
        <Interactive.Div
          name="Closing premise"
          style={{
            position: "absolute",
            left: 108,
            top: 572,
            fontFamily: "Arial, sans-serif",
            fontSize: 45,
            color: "#f3efe5",
          }}
        >
          The right cards are only the beginning.
        </Interactive.Div>
        <Interactive.Div
          name="Repository URL"
          style={{
            position: "absolute",
            left: 108,
            top: 698,
            fontFamily: "Arial, sans-serif",
            fontSize: 39,
            color: "#d0ed58",
          }}
        >
          github.com/ishanvepa/RoyaleBench
        </Interactive.Div>
        <Interactive.Div
          name="Engine credit"
          style={{
            position: "absolute",
            left: 108,
            bottom: 95,
            fontFamily: "Arial, sans-serif",
            fontSize: 27,
            color: "#afb2a3",
          }}
        >
          Built on RoyaleGym / RoyaleSim
        </Interactive.Div>
      </Sequence>
    </>
  );
};
