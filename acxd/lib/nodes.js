'use strict';

/**
 * Small builders for ACXD flow nodes, in the shape the SDK's working examples use.
 *
 * Node ids are derived from the flow id and a readable node name, so a re-run of
 * `deploy.js` updates the same nodes instead of minting new ones.
 */

const crypto = require('crypto');

function nodeId(flowId, name) {
  const h = crypto.createHash('sha1').update(`${flowId}/${name}`).digest('hex');
  const variant = ((parseInt(h[16], 16) & 0x3) | 0x8).toString(16);
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-4${h.slice(13, 16)}-${variant}${h.slice(17, 20)}-${h.slice(20, 32)}`;
}

const statusIs = (value) => ({
  left: { type: 'node_status' },
  operator: 'eq',
  right: { type: 'constant', value },
});

const text = (body) => ({ type: 'text', body, metadata: { alternatePhrasings: [] } });

/** A flow under construction: `add` nodes by name, wire children by name. */
class FlowBuilder {
  constructor(flowId) {
    this.flowId = flowId;
    this.nodes = {};
  }

  id(name) {
    return nodeId(this.flowId, name);
  }

  add(name, type, { children = [], messages = [], metadata = {}, dataRequests, modalities = {} } = {}) {
    const id = this.id(name);
    this.nodes[id] = {
      nodeId: id,
      type,
      childNodes: children.map((c) =>
        typeof c === 'string'
          ? { nodeId: this.id(c), conditions: [] }
          : { nodeId: this.id(c.to), conditions: c.when ?? [], ...(c.name ? { name: c.name } : {}) },
      ),
      messages: messages.map((m) => (typeof m === 'string' ? text(m) : m)),
      modalities,
      metadata: { stateModifications: [], name, ...metadata },
      ...(dataRequests ? { dataRequests } : {}),
    };
    return this;
  }
}

module.exports = { nodeId, statusIs, text, FlowBuilder };
