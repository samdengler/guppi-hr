import {C, Owner} from './theme';

export type P = [number, number];

export type Line = {text: string; mono?: boolean; color?: string};

export type Box = {
  id: string;
  x: number;
  y: number;
  w: number;
  h: number;
  owner: Owner;
  title: string;
  lines: Line[];
  tag?: string;
  dashed?: boolean;
};

export type Chip = {id: string; label: string; mono: boolean; x: number; y: number; w: number; h: number};

export type Edge = {id: string; pts: P[]; ends: [string, string]; dashed?: boolean};

// Main row: y 150 to 310, centre line y 230.
export const ROW_Y = 150;
export const ROW_H = 160;
export const MID = ROW_Y + ROW_H / 2;

export const boxes: Box[] = [
  {id: 'browser', x: 40, y: ROW_Y, w: 220, h: ROW_H, owner: 'net', title: 'Browser', lines: [{text: 'guppi-gpt page'}, {text: '/p/hr/', mono: true}]},
  {id: 'cloudfront', x: 290, y: ROW_Y, w: 236, h: ROW_H, owner: 'net', title: 'CloudFront', lines: [{text: 'chat.dengler.io'}, {text: '/api/hr/*', mono: true}]},
  {id: 'edge', x: 556, y: ROW_Y, w: 286, h: ROW_H, owner: 'agentcore', title: 'Gateway', lines: [{text: 'guppi-gpt-edge', mono: true}, {text: 'WAF, limits, token'}]},
  {id: 'runtime', x: 872, y: ROW_Y, w: 392, h: ROW_H, owner: 'agentcore', title: 'AgentCore Runtime', lines: [{text: 'guppi_connect_bridge', mono: true}, {text: 'bridge: FastAPI', color: C.green}]},
  {id: 'connect', x: 1294, y: ROW_Y, w: 250, h: ROW_H, owner: 'connect', title: 'Amazon Connect', lines: [{text: 'chat per thread'}]},
  {id: 'designer', x: 1580, y: ROW_Y, w: 300, h: 414, owner: 'connect', title: 'Agentic CX designer', lines: []},

  {id: 'okta', x: 40, y: 350, w: 380, h: 150, owner: 'net', title: 'Okta', lines: [{text: 'access token'}, {text: 'aud api://guppi', mono: true}], tag: 'sign-in', dashed: true},
  {id: 'identity', x: 440, y: 350, w: 420, h: 150, owner: 'agentcore', title: 'AgentCore Identity', lines: [{text: 'token exchange'}, {text: 'issuer: Lambda, Rust', color: C.green}], tag: 'chat start only', dashed: true},

  {id: 'agentsGw', x: 920, y: 360, w: 624, h: 106, owner: 'agentcore', title: 'AgentCore Gateway', lines: [{text: 'hr-super-agent-agents', mono: true}]},
  {id: 'profile', x: 920, y: 494, w: 196, h: 106, owner: 'agentcore', title: 'Profile', lines: [{text: 'Haiku 4.5', color: C.violet}]},
  {id: 'pay', x: 1134, y: 494, w: 196, h: 106, owner: 'agentcore', title: 'Pay', lines: [{text: 'Haiku 4.5', color: C.violet}]},
  {id: 'travel', x: 1348, y: 494, w: 196, h: 106, owner: 'agentcore', title: 'Travel', lines: [{text: 'Haiku 4.5', color: C.violet}]},
  {id: 'toolsGw', x: 920, y: 630, w: 624, h: 106, owner: 'agentcore', title: 'AgentCore Gateway + Policy (Cedar)', lines: [{text: 'hr-super-agent-tools', mono: true}]},
  {id: 'toolsRt', x: 920, y: 766, w: 330, h: 106, owner: 'agentcore', title: 'HR tools (MCP)', lines: [{text: 'AgentCore Runtime'}]},
  {id: 'dynamo', x: 1280, y: 766, w: 264, h: 106, owner: 'neutral', title: 'DynamoDB', lines: [{text: 'HR tables'}]},
  {id: 'kb', x: 1606, y: 630, w: 274, h: 106, owner: 'bedrock', title: 'Knowledge base', lines: [{text: 'policy documents'}]},
];

export const boxById = Object.fromEntries(boxes.map((b) => [b.id, b])) as Record<string, Box>;

const chipLabels: [string, string, boolean][] = [
  ['chip-routing', 'Routing model', false],
  ['chip-clarify', 'ClarifyFlow', true],
  ['chip-policy', 'PolicyFlow', true],
  ['chip-profile', 'ProfileFlow', true],
  ['chip-pay', 'PayFlow', true],
  ['chip-travel', 'TravelFlow', true],
];

export const chips: Chip[] = chipLabels.map(([id, label, mono], i) => ({
  id,
  label,
  mono,
  x: 1596,
  y: 252 + i * 50,
  w: 268,
  h: 42,
}));

export const chipCentre = (id: string): P => {
  const c = chips.find((k) => k.id === id)!;
  return [c.x + c.w / 2, c.y + c.h / 2];
};

export const centre = (id: string): P => {
  const b = boxById[id];
  return [b.x + b.w / 2, id === 'designer' ? MID : b.y + b.h / 2];
};

export const edges: Edge[] = [
  {id: 'e1', pts: [[260, MID], [290, MID]], ends: ['browser', 'cloudfront']},
  {id: 'e2', pts: [[526, MID], [556, MID]], ends: ['cloudfront', 'edge']},
  {id: 'e3', pts: [[842, MID], [872, MID]], ends: ['edge', 'runtime']},
  {id: 'e4', pts: [[1264, MID], [1294, MID]], ends: ['runtime', 'connect']},
  {id: 'e5', pts: [[1544, MID], [1580, MID]], ends: ['connect', 'designer']},
  {id: 'eOkta', pts: [[150, 310], [150, 350]], ends: ['browser', 'okta'], dashed: true},
  {id: 'eId', pts: [[892, 310], [892, 425], [860, 425]], ends: ['runtime', 'identity'], dashed: true},
  {id: 'eAg', pts: [[1580, 413], [1544, 413]], ends: ['designer', 'agentsGw']},
  {id: 'eSub1', pts: [[1018, 466], [1018, 494]], ends: ['agentsGw', 'profile']},
  {id: 'eSub2', pts: [[1232, 466], [1232, 494]], ends: ['agentsGw', 'pay']},
  {id: 'eSub3', pts: [[1446, 466], [1446, 494]], ends: ['agentsGw', 'travel']},
  {id: 'eTools', pts: [[1592, 564], [1592, 683], [1544, 683]], ends: ['designer', 'toolsGw']},
  {id: 'eKb', pts: [[1743, 564], [1743, 630]], ends: ['designer', 'kb']},
  {id: 'eTr', pts: [[1085, 736], [1085, 766]], ends: ['toolsGw', 'toolsRt']},
  {id: 'eDb', pts: [[1250, 819], [1280, 819]], ends: ['toolsRt', 'dynamo']},
];

// The alternative: browser wired straight to Connect, above the main row.
export const ALT_Y = 120;
export const altEdge: Edge = {
  id: 'eAlt',
  pts: [[150, ROW_Y], [150, ALT_Y], [1419, ALT_Y], [1419, ROW_Y]],
  ends: ['browser', 'connect'],
};

export const polyLength = (pts: P[]) => {
  let total = 0;
  for (let i = 1; i < pts.length; i++) {
    total += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
  }
  return total;
};

export const along = (pts: P[], t: number): P => {
  if (pts.length === 1) return pts[0];
  const total = polyLength(pts);
  let d = Math.max(0, Math.min(1, t)) * total;
  for (let i = 1; i < pts.length; i++) {
    const [x0, y0] = pts[i - 1];
    const [x1, y1] = pts[i];
    const len = Math.hypot(x1 - x0, y1 - y0);
    if (d <= len || i === pts.length - 1) {
      const f = len === 0 ? 1 : Math.min(1, d / len);
      return [x0 + (x1 - x0) * f, y0 + (y1 - y0) * f];
    }
    d -= len;
  }
  return pts[pts.length - 1];
};

export const pathD = (pts: P[]) => pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p[0]},${p[1]}`).join(' ');
