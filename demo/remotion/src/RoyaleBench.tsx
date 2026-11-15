import { AbsoluteFill, Sequence, Track, useVideoConfig } from "remotion";
import {
  Attempt,
  ColdOpen,
  Decision,
  Ending,
  Method,
  Placements,
  Reference,
  Results,
  Setup,
} from "./Scenes";
import { ink, paper } from "./design";

export const RoyaleBench = () => {
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill style={{ backgroundColor: paper }}>
      <Track name="The edit">
        <Sequence
          name="Cold open · the loss"
          durationInFrames={4 * fps}
          style={{ backgroundColor: ink }}
        >
          <ColdOpen />
        </Sequence>
        <Sequence name="The position" from={4 * fps} durationInFrames={5 * fps}>
          <Setup />
        </Sequence>
        <Sequence
          name="Opus attempt"
          from={9 * fps}
          durationInFrames={12 * fps}
          style={{ backgroundColor: ink }}
        >
          <Attempt />
        </Sequence>
        <Sequence
          name="Freeze · offensive Log"
          from={21 * fps}
          durationInFrames={4 * fps}
        >
          <Decision />
        </Sequence>
        <Sequence
          name="Validated reference"
          from={25 * fps}
          durationInFrames={13 * fps}
          style={{ backgroundColor: ink }}
        >
          <Reference />
        </Sequence>
        <Sequence
          name="Placement comparison"
          from={38 * fps}
          durationInFrames={11 * fps}
        >
          <Placements />
        </Sequence>
        <Sequence
          name="Agent interface"
          from={49 * fps}
          durationInFrames={9 * fps}
          style={{ backgroundColor: ink }}
        >
          <Method />
        </Sequence>
        <Sequence
          name="Measured result"
          from={58 * fps}
          durationInFrames={10 * fps}
        >
          <Results />
        </Sequence>
        <Sequence
          name="Winning connection and end card"
          from={68 * fps}
          durationInFrames={8 * fps}
          style={{ backgroundColor: ink }}
        >
          <Ending />
        </Sequence>
      </Track>
    </AbsoluteFill>
  );
};
