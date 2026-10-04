import {loadFont as loadSans} from '@remotion/google-fonts/IBMPlexSans';
import {loadFont as loadMono} from '@remotion/google-fonts/IBMPlexMono';

const sans = loadSans('normal', {weights: ['400', '600'], subsets: ['latin']});
const mono = loadMono('normal', {weights: ['400', '500'], subsets: ['latin']});

export const SANS = `${sans.fontFamily}, "Helvetica Neue", Arial, sans-serif`;
export const MONO = `${mono.fontFamily}, Menlo, monospace`;

// Theme tokens shared with the static architecture diagram.
export const C = {
  bg: '#11161c',
  panel: '#171e26',
  text: '#e3e9ef',
  muted: '#98a6b4',
  line: '#2a3541',
  grey: '#7f8c99', // Internet and CloudFront
  blue: '#4f8fd6', // AgentCore: Gateway, Runtime, Identity
  amber: '#e5a84a', // Amazon Connect and its Agentic CX designer
  green: '#5fbf8a', // our code: the bridge, the sub-agents' prompts
  violet: '#b48ce0', // Bedrock models
};

export type Owner = 'net' | 'agentcore' | 'connect' | 'ours' | 'bedrock' | 'neutral';

export const ownerColor: Record<Owner, string> = {
  net: C.grey,
  agentcore: C.blue,
  connect: C.amber,
  ours: C.green,
  bedrock: C.violet,
  neutral: C.muted,
};

// Time categories for the stacked bar.
export type Cat = 'connect' | 'agentcore' | 'net' | 'ours' | 'bedrock';

export const catColor: Record<Cat, string> = {
  connect: C.amber,
  agentcore: C.blue,
  net: C.grey,
  ours: C.green,
  bedrock: C.violet,
};

export const catLabel: Record<Cat, string> = {
  connect: 'Connect and designer',
  agentcore: 'AgentCore',
  net: 'Internet and CloudFront',
  ours: 'Bridge code',
  bedrock: 'Bedrock model',
};

export const FPS = 30;
export const W = 1920;
export const H = 1080;
