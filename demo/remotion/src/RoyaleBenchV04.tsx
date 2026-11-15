import { AbsoluteFill, Sequence, Track, useVideoConfig } from "remotion";
import { Audio } from "@remotion/media";
import { staticFile } from "remotion";
import { CaptionTrack, GameStage } from "./GameUI";
import {
  AgentInterface, CannonDecision, Closing, LogDecision, Opening, Position,
  RunResult, SynchronizedAttempts,
} from "./GameScenes";

export const RoyaleBenchV04 = () => {
  const { fps } = useVideoConfig();
  return (
    <GameStage>
      <Track name="The game edit">
        <Sequence name="Cold open" durationInFrames={4 * fps}>
          <Opening />
        </Sequence>
        <Sequence name="The benchmark task and agent loop" from={4 * fps} durationInFrames={9 * fps}>
          <Position />
        </Sequence>
        <Sequence name="Text observation and coordinate action" from={13 * fps} durationInFrames={11 * fps}>
          <AgentInterface />
        </Sequence>
        <Sequence name="Synchronized attempts" from={24 * fps} durationInFrames={13 * fps}>
          <SynchronizedAttempts />
        </Sequence>
        <Sequence name="Matched Cannon placement" from={37 * fps} durationInFrames={6 * fps}>
          <CannonDecision />
        </Sequence>
        <Sequence name="Matched Log target" from={43 * fps} durationInFrames={7 * fps}>
          <LogDecision />
        </Sequence>
        <Sequence name="Measured result" from={50 * fps} durationInFrames={9 * fps}>
          <RunResult />
        </Sequence>
        <Sequence name="Winning connection and end card" from={59 * fps} durationInFrames={8 * fps}>
          <Closing />
        </Sequence>
      </Track>
      <AbsoluteFill style={{ pointerEvents: "none" }}>
        <CaptionTrack />
      </AbsoluteFill>
      <Audio src={staticFile("media/sfx-v04.wav")} volume={1} />
    </GameStage>
  );
};
