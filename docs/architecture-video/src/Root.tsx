import React from 'react';
import {Composition, Sequence, AbsoluteFill} from 'remotion';
import {C, FPS, W, H} from './theme';
import {TitleScene, MapScene, PageLoadScene, QuestionAScene, QuestionBScene, AlternativeScene, CloseScene} from './scenes';

// Scene lengths in frames at 30 fps.
export const SCENES: [string, React.FC, number][] = [
  ['Title', TitleScene, 90],
  ['Map', MapScene, 330],
  ['PageLoad', PageLoadScene, 270],
  ['QuestionA', QuestionAScene, 900],
  ['QuestionB', QuestionBScene, 380],
  ['Alternative', AlternativeScene, 480],
  ['Close', CloseScene, 150],
];

const TOTAL = SCENES.reduce((s, [, , d]) => s + d, 0);

const Video: React.FC = () => {
  let from = 0;
  return (
    <AbsoluteFill style={{background: C.bg}}>
      {SCENES.map(([name, Scene, dur]) => {
        const seq = (
          <Sequence key={name} name={name} from={from} durationInFrames={dur}>
            <Scene />
          </Sequence>
        );
        from += dur;
        return seq;
      })}
    </AbsoluteFill>
  );
};

export const RemotionRoot: React.FC = () => (
  <Composition id="HrQuestionFlow" component={Video} durationInFrames={TOTAL} fps={FPS} width={W} height={H} />
);
