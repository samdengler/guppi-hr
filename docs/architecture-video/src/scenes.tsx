import React from 'react';
import {AbsoluteFill, useCurrentFrame, interpolate} from 'remotion';
import {C, SANS, MONO, Cat, catColor} from './theme';
import {MID, chipCentre, ALT_Y, P} from './layout';
import {
  MapView,
  Header,
  Panel,
  CaptionView,
  Caption,
  Bar,
  OwnerLegend,
  Step,
  runSteps,
  fade,
  zeroCats,
} from './parts';

const Bg: React.FC<{children: React.ReactNode}> = ({children}) => (
  <AbsoluteFill style={{background: C.bg, fontFamily: SANS, color: C.text}}>{children}</AbsoluteFill>
);

// The ten measured steps of question A add to 1.752 s; the measured time to
// first words is 1.74 s. The clock scales each step by K so it ends on 1.74 s.
const K = 1.74 / 1.752;

const X = {
  browser: 150,
  edge: 699,
  runtime: 1068,
  connect: 1419,
  designerIn: 1600,
};
const ROUTING = chipCentre('chip-routing');
const CLARIFY = chipCentre('chip-clarify');
const PROFILE_CHIP = chipCentre('chip-profile');

// ---------- Scene 1: title ----------

export const TitleScene: React.FC = () => {
  const f = useCurrentFrame();
  const a = fade(f, 0, 15) * (1 - fade(f, 78, 12));
  return (
    <Bg>
      <div style={{position: 'absolute', left: 160, top: 380, opacity: a}}>
        <div style={{fontSize: 34, color: C.muted, marginBottom: 18}}>HR assistant</div>
        <div style={{fontSize: 80, fontWeight: 600, lineHeight: '96px'}}>
          One question on <span style={{fontFamily: MONO, fontWeight: 500, color: C.amber}}>chat.dengler.io/p/hr/</span>
        </div>
        <div style={{fontSize: 34, color: C.muted, marginTop: 28}}>The parts, the path, and where the time goes. Measured 4 Oct 2026, us-east-1.</div>
      </div>
    </Bg>
  );
};

// ---------- Scene 2: the map ----------

const BUILD: [string, number][] = [
  ['browser', 10],
  ['cloudfront', 22],
  ['edge', 34],
  ['runtime', 46],
  ['connect', 58],
  ['designer', 70],
  ['chip-routing', 80],
  ['chip-clarify', 88],
  ['chip-policy', 96],
  ['chip-profile', 104],
  ['chip-pay', 112],
  ['chip-travel', 120],
  ['agentsGw', 134],
  ['profile', 144],
  ['pay', 150],
  ['travel', 156],
  ['toolsGw', 170],
  ['toolsRt', 182],
  ['dynamo', 190],
  ['kb', 202],
  ['okta', 218],
  ['identity', 232],
];
const buildAt = Object.fromEntries(BUILD);

const MAP_NOTES: [number, string][] = [
  [10, 'A question travels left to right, from the browser to the Agentic CX designer inside Amazon Connect.'],
  [134, 'Below the designer: three sub-agents, the HR tools behind Policy, and the knowledge base.'],
  [218, 'Okta signs the employee in. Identity exchanges tokens only when a chat starts.'],
];

export const MapScene: React.FC = () => {
  const f = useCurrentFrame();
  const appear = (id: string) => fade(f, buildAt[id] ?? 0, 12);
  return (
    <Bg>
      <Header title="The parts, colored by owner" a={fade(f, 0, 10)} />
      <MapView s={{appear}} />
      <Panel a={fade(f, 6, 10)}>
        {MAP_NOTES.map(([at, text]) => (
          <div key={at} style={{fontSize: 30, lineHeight: '40px', color: C.text, marginBottom: 22, opacity: fade(f, at, 12)}}>
            {text}
          </div>
        ))}
      </Panel>
      <OwnerLegend a={fade(f, 246, 15)} />
    </Bg>
  );
};

// ---------- Scene 3: page load ----------

const WARM: {at: number; label: string; time: string; color: string; glow: string[]; edges: string[]}[] = [
  {at: 20, label: 'Token exchange: Identity and the issuer', time: '0.4 s', color: C.blue, glow: ['identity', 'runtime'], edges: ['eId']},
  {at: 66, label: 'StartChatContact', time: '0.5 s', color: C.amber, glow: ['connect'], edges: ['e4']},
  {at: 112, label: 'WebSocket and the greeting', time: '1.3 s', color: C.amber, glow: ['connect', 'designer'], edges: ['e5']},
  {at: 158, label: 'Warm 3 sub-agents (background)', time: '6 to 8 s', color: C.blue, glow: ['agentsGw', 'profile', 'pay', 'travel'], edges: ['eAg', 'eSub1', 'eSub2', 'eSub3']},
];

export const PageLoadScene: React.FC = () => {
  const f = useCurrentFrame();
  let idx = -1;
  WARM.forEach((w, i) => {
    if (f >= w.at) idx = i;
  });
  const glow: Record<string, {color: string; k: number}> = {};
  const edgeGlow: Record<string, {color: string; k: number}> = {};
  if (idx >= 0 && f < 205) {
    const w = WARM[idx];
    const k = fade(f, w.at, 8);
    w.glow.forEach((id) => (glow[id] = {color: w.color, k}));
    w.edges.forEach((id) => (edgeGlow[id] = {color: w.color, k}));
  }
  return (
    <Bg>
      <Header title="Page load: the warm start, before any question" a={fade(f, 0, 10)} />
      <MapView s={{glow, edgeGlow}} />
      <Panel h={360}>
        <div style={{fontSize: 28, color: C.muted, lineHeight: '36px', marginBottom: 8}}>The bridge starts the chat when the page opens</div>
        {WARM.map((w) => (
          <div
            key={w.at}
            style={{display: 'flex', justifyContent: 'space-between', fontSize: 30, lineHeight: '42px', opacity: fade(f, w.at, 10)}}
          >
            <span style={{color: C.text}}>{w.label}</span>
            <span style={{fontFamily: MONO, color: w.color}}>{w.time}</span>
          </div>
        ))}
        <div style={{fontSize: 30, fontWeight: 600, lineHeight: '40px', color: C.green, marginTop: 14, opacity: fade(f, 205, 12)}}>
          Chat ready about 4 s after the page opens; the reader is still reading.
        </div>
      </Panel>
      <OwnerLegend a={1} />
    </Bg>
  );
};

// ---------- Scene 4: question A ----------

const A0 = 50;
const AS = 75;
const at = (i: number) => A0 + i * AS;

export const stepsA: Step[] = [
  {
    start: at(0), travel: 32, k: K, color: C.grey, path: [[X.browser, MID], [X.edge, MID]], add: {net: 0.14}, glow: ['cloudfront', 'edge'], edges: ['e1', 'e2'],
    caption: {kicker: 'Step 1 of 10', owner: 'Internet and CloudFront', ownerColor: C.grey, title: 'Browser to CloudFront to the edge gateway', time: '0.14 s', note: 'The round trip both ways is 0.27 s, split about evenly.'},
  },
  {
    start: at(1), travel: 20, k: K, color: C.blue, add: {agentcore: 0.007}, glow: ['edge'],
    caption: {kicker: 'Step 2 of 10', owner: 'AgentCore Gateway', ownerColor: C.blue, title: "Edge gateway's own work", time: '0.007 s', note: 'AWS WAF, per-user limits, Okta token check, target "hr".'},
  },
  {
    start: at(2), travel: 32, k: K, color: C.blue, path: [[X.edge, MID], [X.runtime, MID]], add: {agentcore: 0.35}, glow: ['runtime'], edges: ['e3'],
    caption: {kicker: 'Step 3 of 10', owner: 'AgentCore Runtime', ownerColor: C.blue, title: "Gateway to the bridge's container", time: '0.35 s', note: 'One microVM per browser session. Median 0.28 s, range 0.26 to 0.38 s.'},
  },
  {
    start: at(3), travel: 20, k: K, color: C.green, add: {ours: 0.025}, glow: ['runtime'],
    caption: {kicker: 'Step 4 of 10', owner: 'Our code', ownerColor: C.green, title: 'Bridge code', time: '0.025 s', note: "Python 3.12, FastAPI. Looks up the thread's Connect chat in DynamoDB."},
  },
  {
    start: at(4), travel: 32, k: K, color: C.amber, path: [[X.runtime, MID], [X.connect, MID]], add: {connect: 0.19}, glow: ['connect'], edges: ['e4'],
    caption: {kicker: 'Step 5 of 10', owner: 'Amazon Connect', ownerColor: C.amber, title: 'SendMessage', time: '0.19 s', note: "Participant API call into the thread's chat contact."},
  },
  {
    start: at(5), travel: 32, k: K, color: C.amber, path: [[X.connect, MID], [X.designerIn, MID], ROUTING], add: {connect: 0.24}, glow: ['designer'], edges: ['e5'],
    caption: {kicker: 'Step 6 of 10', owner: 'Amazon Connect', ownerColor: C.amber, title: 'Connect hands the message to the designer', time: '0.24 s'},
  },
  {
    start: at(6), travel: 36, k: K, color: C.amber, add: {connect: 0.41}, glow: ['chip-routing'],
    caption: {kicker: 'Step 7 of 10', owner: 'Agentic CX designer', ownerColor: C.amber, title: 'Routing model', time: '0.41 s', note: 'Picks the flow for this question: ClarifyFlow.'},
  },
  {
    start: at(7), travel: 20, k: K, color: C.amber, path: [ROUTING, CLARIFY], add: {connect: 0.08}, glow: ['chip-clarify'],
    caption: {kicker: 'Step 8 of 10', owner: 'Agentic CX designer', ownerColor: C.amber, title: 'Flow steps', time: '0.08 s', note: 'ClarifyFlow asks a fixed question.'},
  },
  {
    start: at(8), travel: 34, k: K, color: C.amber, path: [CLARIFY, [X.designerIn, CLARIFY[1]], [X.designerIn, MID], [X.connect, MID], [X.runtime, MID]], add: {connect: 0.18}, glow: ['connect', 'runtime'], edges: ['e5', 'e4'],
    caption: {kicker: 'Step 9 of 10', owner: 'Amazon Connect', ownerColor: C.amber, title: 'Reply over the WebSocket', time: '0.18 s', note: 'Connect pushes the reply to the bridge.'},
  },
  {
    start: at(9), travel: 36, k: K, color: C.grey, path: [[X.runtime, MID], [X.browser, MID]], add: {net: 0.13}, glow: ['browser'], edges: ['e3', 'e2', 'e1'],
    caption: {kicker: 'Step 10 of 10', owner: 'Internet and AgentCore', ownerColor: C.grey, title: 'Bridge to the browser', time: '0.13 s', note: 'Back through the runtime, the gateway and CloudFront. First words on screen.'},
  },
];

const A_END = at(10); // 800

const TOTALS: [Cat, string, string, string][] = [
  ['connect', 'Connect and designer', '1.10 s', '63%'],
  ['agentcore', 'AgentCore Runtime', '0.35 s', '20%'],
  ['net', 'Internet and CloudFront', '0.27 s', '15%'],
  ['ours', 'Bridge code', '0.035 s', '2%'],
];

const QuestionIntro: React.FC<{f: number; text: string; sub: string}> = ({f, text, sub}) => (
  <div style={{opacity: fade(f, 4, 10)}}>
    <div style={{fontSize: 28, color: C.muted, lineHeight: '36px'}}>The employee types</div>
    <div style={{fontSize: 40, fontWeight: 600, lineHeight: '52px', marginTop: 8}}>"{text}"</div>
    <div style={{fontSize: 30, color: C.muted, lineHeight: '40px', marginTop: 18}}>{sub}</div>
  </div>
);

export const QuestionAScene: React.FC = () => {
  const f = useCurrentFrame();
  const r = runSteps(f, stepsA);
  const showTotals = f >= A_END;
  const clock = showTotals ? 1.74 : r.clock;
  return (
    <Bg>
      <Header title={'Question A: "I need to update my information"'} a={fade(f, 0, 10)} clock={clock} />
      <MapView s={{glow: showTotals ? {} : r.glow, edgeGlow: showTotals ? {} : r.edgeGlow, dot: r.dot}} />
      <Panel>
        {r.current < 0 ? (
          <QuestionIntro f={f} text="I need to update my information" sub="ClarifyFlow answers. Ten steps to the first words." />
        ) : !showTotals && r.caption ? (
          <CaptionView c={r.caption} a={r.captionA} />
        ) : null}
        {showTotals ? (
          <div style={{opacity: fade(f, A_END, 10)}}>
            <div style={{fontSize: 38, fontWeight: 600, lineHeight: '48px', marginBottom: 14}}>1.74 s to first words</div>
            {TOTALS.map(([c, label, secs, pct]) => (
              <div key={c} style={{display: 'flex', alignItems: 'center', fontSize: 30, lineHeight: '50px'}}>
                <div style={{width: 26, height: 26, borderRadius: 5, background: catColor[c], marginRight: 16}} />
                <span style={{flex: 1}}>{label}</span>
                <span style={{fontFamily: MONO, color: C.muted, width: 150, textAlign: 'right'}}>{secs}</span>
                <span style={{fontFamily: MONO, fontWeight: 500, color: catColor[c], width: 110, textAlign: 'right'}}>{pct}</span>
              </div>
            ))}
          </div>
        ) : null}
      </Panel>
      <Bar values={showTotals ? {connect: 1.1, agentcore: 0.35, net: 0.27, ours: 0.035, bedrock: 0} : r.cats} scale={1.8} a={1} />
    </Bg>
  );
};

// ---------- Scene 5: question B ----------

const PROFILE_BOX: P = [1018, 547];
const AG_Y = 413;

const stepsB: Step[] = [
  {
    start: 40, travel: 60, k: K, color: C.text, path: [[X.browser, MID], [X.connect, MID], [X.designerIn, MID], ROUTING],
    add: {net: 0.14, agentcore: 0.357, ours: 0.025, connect: 0.84}, glow: ['chip-routing'], edges: ['e1', 'e2', 'e3', 'e4', 'e5'],
    caption: {kicker: 'Steps 1 to 7', title: 'Same path as question A, up to the routing model', time: '1.35 s', note: 'The routing model picks ProfileFlow.'},
  },
  {
    start: 112, travel: 44, color: C.blue, path: [ROUTING, [PROFILE_CHIP[0], AG_Y], [PROFILE_BOX[0], AG_Y], PROFILE_BOX],
    add: {agentcore: 0.38}, glow: ['chip-profile', 'agentsGw', 'profile'], edges: ['eAg', 'eSub1'],
    caption: {kicker: 'ProfileFlow delegates', owner: 'AgentCore Gateway', ownerColor: C.blue, title: 'Agents gateway into the Profile sub-agent', time: '0.35 to 0.42 s', note: 'hr-super-agent-agents, then Runtime hr_super_agent_profile.'},
  },
  {
    start: 170, travel: 64, color: C.violet, add: {bedrock: 0.85}, glow: ['profile'],
    caption: {kicker: 'Profile sub-agent (Strands)', owner: 'Bedrock model', ownerColor: C.violet, title: 'One Haiku call, its record already in the prompt', time: '0.85 s'},
  },
  {
    start: 246, travel: 30, color: C.blue, path: [PROFILE_BOX, [PROFILE_BOX[0], AG_Y], [PROFILE_CHIP[0], AG_Y], PROFILE_CHIP],
    add: {agentcore: 0.13}, glow: ['agentsGw', 'chip-profile'], edges: ['eSub1', 'eAg'],
    caption: {kicker: 'Back to ProfileFlow', owner: 'AgentCore Gateway', ownerColor: C.blue, title: 'Sub-agent answer returns to the designer', time: '0.06 to 0.19 s'},
  },
  {
    start: 284, travel: 36, k: K, color: C.amber, path: [PROFILE_CHIP, [X.designerIn, PROFILE_CHIP[1]], [X.designerIn, MID], [X.browser, MID]],
    add: {connect: 0.26, net: 0.13}, glow: ['browser'], edges: ['e5', 'e4', 'e3', 'e2', 'e1'],
    caption: {kicker: 'Steps 8 to 10', title: 'Reply to the browser, as in question A', time: '0.39 s'},
  },
];

const B_END = 326;

export const QuestionBScene: React.FC = () => {
  const f = useCurrentFrame();
  const r = runSteps(f, stepsB);
  const done = f >= B_END;
  return (
    <Bg>
      <Header title={'Question B: "I need to change my home address"'} a={fade(f, 0, 10)} clock={done ? 3.1 : r.clock} />
      <MapView s={{glow: done ? {} : r.glow, edgeGlow: done ? {} : r.edgeGlow, dot: r.dot}} />
      <Panel>
        {r.current < 0 ? (
          <QuestionIntro f={f} text="I need to change my home address" sub="ProfileFlow hands the question to the Profile sub-agent." />
        ) : !done && r.caption ? (
          <CaptionView c={r.caption} a={r.captionA} />
        ) : null}
        {done ? (
          <CaptionView
            a={fade(f, B_END, 10)}
            c={{kicker: 'Question B', title: 'About 3.1 s to first words', note: 'The question A path, 1.74 s, plus about 1.4 s through the agents gateway and the Profile sub-agent.'}}
          />
        ) : null}
      </Panel>
      <Bar values={r.cats} scale={3.2} a={1} show={['connect', 'agentcore', 'net', 'ours', 'bedrock']} />
    </Bg>
  );
};

// ---------- Scene 6: the alternative ----------

const stepsAlt: Step[] = [
  {
    start: 80, travel: 44, k: K, color: C.amber, path: [[X.browser, MID], [X.browser, ALT_Y], [X.connect, ALT_Y], [X.connect, MID]],
    add: {net: 0.14, connect: 0.19}, glow: ['connect', 'browser'], edges: ['eAlt'],
    caption: {kicker: 'Each question', owner: 'Internet and Connect', ownerColor: C.amber, title: 'Browser to Connect: SendMessage', time: 'about 0.33 s', note: "Sent with the chat's participant token."},
  },
  {
    start: 130, travel: 26, k: K, color: C.amber, path: [[X.connect, MID], [X.designerIn, MID], ROUTING], add: {connect: 0.24}, glow: ['designer'], edges: ['e5'],
    caption: {kicker: 'Unchanged', owner: 'Amazon Connect', ownerColor: C.amber, title: 'Connect hands the message to the designer', time: '0.24 s'},
  },
  {
    start: 160, travel: 26, k: K, color: C.amber, add: {connect: 0.41}, glow: ['chip-routing'],
    caption: {kicker: 'Unchanged', owner: 'Agentic CX designer', ownerColor: C.amber, title: 'Routing model', time: '0.41 s'},
  },
  {
    start: 190, travel: 16, k: K, color: C.amber, path: [ROUTING, CLARIFY], add: {connect: 0.08}, glow: ['chip-clarify'],
    caption: {kicker: 'Unchanged', owner: 'Agentic CX designer', ownerColor: C.amber, title: 'Flow steps: ClarifyFlow', time: '0.08 s'},
  },
  {
    start: 212, travel: 44, color: C.amber,
    path: [CLARIFY, [X.designerIn, CLARIFY[1]], [X.designerIn, MID], [X.connect, MID], [X.connect, ALT_Y], [X.browser, ALT_Y], [X.browser, MID]],
    add: {connect: 0.18, net: 0.07}, k: (0.18 * K + 0.07) / 0.25, glow: ['browser'], edges: ['e5', 'eAlt'],
    caption: {kicker: 'Each question', owner: 'Amazon Connect', ownerColor: C.amber, title: "Reply over the browser's own WebSocket", time: 'about 0.25 s'},
  },
];

const ALT_RESULT = 264;
const ALT_LIST = 330;

const GIVES_UP = [
  "AWS WAF at the edge gateway",
  'Per-user limits',
  "The gateway's Okta token check",
  'AgentCore Runtime in the question path',
];

export const AlternativeScene: React.FC = () => {
  const f = useCurrentFrame();
  const r = runSteps(f, stepsAlt);
  const dimK = fade(f, 10, 20);
  const dimV = 1 - 0.75 * dimK;
  const dim = {cloudfront: dimV, edge: dimV, runtime: dimV, e1: dimV, e2: dimV, e3: dimV, e4: dimV};
  const alt = interpolate(f, [24, 60], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const result = f >= ALT_RESULT;
  const listA = fade(f, ALT_LIST, 14);
  return (
    <Bg>
      <Header title="Alternative, not built: the browser talks to Connect" a={fade(f, 0, 10)} clock={result ? 1.3 : r.clock} />
      <MapView s={{glow: result ? {} : r.glow, edgeGlow: result ? {} : r.edgeGlow, dot: r.dot, dim, alt}} />
      <Panel>
        {r.current < 0 ? (
          <div style={{opacity: fade(f, 6, 10)}}>
            <div style={{fontSize: 28, color: C.muted, lineHeight: '36px'}}>Page load stays the same</div>
            <div style={{fontSize: 32, lineHeight: '44px', marginTop: 10}}>
              The bridge still starts the chat at page load, then hands the browser the chat's participant token.
            </div>
            <div style={{fontSize: 30, lineHeight: '40px', color: C.muted, marginTop: 16}}>Gateway, runtime and CloudFront drop out of each question.</div>
          </div>
        ) : !result && r.caption ? (
          <CaptionView c={r.caption} a={r.captionA} />
        ) : null}
        {result ? (
          <CaptionView
            a={fade(f, ALT_RESULT, 10)}
            c={{kicker: 'Question A without the gateway hop', title: 'About 1.3 s to first words', time: '1.2 to 1.4 s', ownerColor: C.text, note: 'Removes steps 2, 3 and 4 and the AgentCore part of step 10: 0.35 to 0.6 s per question.'}}
          />
        ) : null}
      </Panel>
      <Bar values={r.cats} scale={1.8} a={1} ghost={{secs: 1.74, label: 'Question A today: 1.74 s'}} />
      {listA > 0 ? (
        <Panel x={40} y={318} w={1504} h={554} a={listA}>
          <div style={{fontSize: 38, fontWeight: 600, lineHeight: '50px', marginBottom: 16}}>Given up on each question</div>
          {GIVES_UP.map((t, i) => (
            <div key={t} style={{display: 'flex', alignItems: 'center', fontSize: 34, lineHeight: '54px', opacity: fade(f, ALT_LIST + 12 + i * 14, 10)}}>
              <div style={{width: 14, height: 14, borderRadius: 7, background: C.blue, marginRight: 22}} />
              {t}
            </div>
          ))}
          <div style={{fontSize: 32, lineHeight: '46px', color: C.amber, marginTop: 20, opacity: fade(f, ALT_LIST + 76, 10)}}>
            Kept: Connect still checks the participant token.
          </div>
          <div style={{fontSize: 30, lineHeight: '44px', color: C.muted, marginTop: 10, opacity: fade(f, ALT_LIST + 92, 10)}}>
            The chosen stack is Gateway + Policy + Identity + Runtime. Not built; Sam's call.
          </div>
        </Panel>
      ) : null}
    </Bg>
  );
};

// ---------- Scene 7: close ----------

const CLOSE: [Cat, string, number][] = [
  ['connect', 'Connect and its designer', 63],
  ['agentcore', 'AgentCore Runtime', 20],
  ['net', 'Internet', 15],
  ['ours', 'Bridge code', 2],
];

export const CloseScene: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <Bg>
      <div style={{position: 'absolute', left: 160, top: 200, opacity: fade(f, 0, 12)}}>
        <div style={{fontSize: 36, color: C.muted, marginBottom: 40}}>Where question A's 1.74 s goes</div>
        {CLOSE.map(([c, label, pct], i) => {
          const a = fade(f, 8 + i * 10, 12);
          return (
            <div key={c} style={{display: 'flex', alignItems: 'center', height: 110, opacity: a}}>
              <div style={{width: 640, fontSize: 52, fontWeight: 600}}>{label}:</div>
              <div style={{width: 170, fontFamily: MONO, fontWeight: 500, fontSize: 60, color: catColor[c], textAlign: 'right', marginRight: 40}}>
                {pct}%
              </div>
              <div style={{width: Math.max(10, pct * 12 * a), height: 46, background: catColor[c], borderRadius: 6}} />
            </div>
          );
        })}
      </div>
    </Bg>
  );
};

export {zeroCats};
