import { Composition, staticFile } from "remotion";
import { loadFont } from "@remotion/fonts";
import { RoyaleBench } from "./RoyaleBench";
import "./style.css";

loadFont({
  family: "ReplayDisplay",
  url: staticFile("fonts/impact.ttf"),
  weight: "400",
});

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="RoyaleBench"
        component={RoyaleBench}
        durationInFrames={2160}
        fps={30}
        width={1920}
        height={1080}
      />
    </>
  );
};
