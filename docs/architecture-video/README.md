# HR question flow video

A Remotion animation of how one question flows through the HR assistant at
chat.dengler.io/p/hr/. Composition id: `HrQuestionFlow` (1920x1080, 30 fps, about 87 s).

- Install: `npm install`
- Preview in Remotion Studio: `npm run preview`
- Render the video: `npx remotion render HrQuestionFlow out/hr-question-flow.mp4`
- Render one frame: `npx remotion still HrQuestionFlow out/still.png --frame=930`

Scene lengths are in `src/Root.tsx`; the layout and names are in `src/layout.ts`;
the measured timings are in `src/scenes.tsx`.
