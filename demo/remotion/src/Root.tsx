import { Composition, staticFile } from "remotion";
import { loadFont } from "@remotion/fonts";
import { RoyaleBenchV04 } from "./RoyaleBenchV04";
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
        component={RoyaleBenchV04}
        durationInFrames={2010}
        fps={30}
        width={1920}
        height={1080}
      />
    </>
  );
};
