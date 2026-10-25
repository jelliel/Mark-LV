/**
 * data.js — fetching the skeleton + the live observer socket.
 *
 * One direction of dependency: nothing here imports three.js. The scene
 * reads from this module; this module knows nothing about the scene.
 */

const API_BASE = '';                 // same origin
const WS_PATH = '/ws/observe';

export const state = {
  regions: [],
  nodes: [],
  edges: [],
  stats: {},
  /** id → node, for O(1) lookup when events name a node */
  byId: new Map(),
  /** id → live activity: { active, startedAt, lastSeen } */
  activity: new Map(),
};

export const handlers = {
  onNodeRecall: [],
  onNodeWrite: [],
  onAgentDispatch: [],
  onAgentDone: [],
  onTurnComplete: [],
  onAlert: [],
  onMindMap: [],
};

/** Fire every callback registered for a kind. */
export function emit(kind, payload) {
  for (const fn of handlers[kind] || []) {
    try { fn(payload); } catch (e) { console.error(`[mind] handler for ${kind} failed`, e); }
  }
}

/** Rebuild the id → node index. */
function reindex() {
  state.byId.clear();
  for (const n of state.nodes) state.byId.set(n.id, n);
}

/**
 * Fetch the skeleton once. Throws on failure — a silent black page is the
 * worst outcome for a page whose whole job is showing what is there.
 */
export async function loadSkeleton() {
  const res = await fetch(`${API_BASE}/api/mind-map`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`mind-map fetch failed: HTTP ${res.status}`);
  const data = await res.json();
  applySkeleton(data);
  return data;
}

export function applySkeleton(data) {
  state.regions = data.regions || [];
  state.nodes = data.nodes || [];
  state.edges = data.edges || [];
  state.stats = data.stats || {};
  reindex();
  emit('onMindMap', state);
}

/**
 * Connect the read-only observer socket. Reconnects with exponential backoff
 * (1s doubling to a 15s cap) and closes entirely while the tab is hidden —
 * the render loop is paused anyway, and a live socket would queue a stale
 * burst to replay on return.
 */
let socket = null;
let backoff = 1000;
let reconnectTimer = null;
let manualClose = false;

export function connect() {
  if (socket && (socket.readyState === WebSocket.OPEN ||
                 socket.readyState === WebSocket.CONNECTING)) return;

  manualClose = false;
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  socket = new WebSocket(`${proto}://${location.host}${WS_PATH}`);

  socket.onopen = () => {
    backoff = 1000;
    console.info('[mind] observer connected');
  };

  socket.onmessage = (ev) => {
    let msg;
    try { msg = JSON.parse(ev.data); } catch (e) { return; }
    handleEvent(msg);
  };

  socket.onclose = () => {
    socket = null;
    if (manualClose) return;
    console.info(`[mind] observer closed — reconnecting in ${backoff / 1000}s`);
    clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(connect, backoff);
    backoff = Math.min(backoff * 2, 15000);
  };

  socket.onerror = () => { /* onclose does the recovery */ };
}

export function disconnect() {
  manualClose = true;
  clearTimeout(reconnectTimer);
  if (socket) { socket.close(); socket = null; }
}

/**
 * Map a server event to motion. Events that name a node we don't have are
 * dropped silently — an animation flying between two points that mean
 * nothing is a lie.
 */
function handleEvent(msg) {
  switch (msg.type) {
    case 'mind_map':
      applySkeleton(msg);
      break;

    case 'recall': {
      const node = state.byId.get(msg.node);
      if (!node) return;              // no fake pulses
      emit('onNodeRecall', node);
      break;
    }

    case 'write': {
      const node = state.byId.get(msg.node);
      emit('onNodeWrite', node || { id: msg.node, label: msg.label || msg.node });
      break;
    }

    case 'agent_dispatch': {
      const node = state.byId.get(msg.node) ||
                   state.byId.get(`agent:${slug(msg.agent)}`);
      if (!node) return;
      state.activity.set(node.id, {
        active: true,
        startedAt: performance.now(),
        lastSeen: performance.now(),
      });
      emit('onAgentDispatch', node);
      break;
    }

    case 'agent_done': {
      const node = state.byId.get(msg.node) ||
                   state.byId.get(`agent:${slug(msg.agent)}`);
      if (!node) return;
      const a = state.activity.get(node.id) || {};
      state.activity.set(node.id, { ...a, active: false, lastSeen: performance.now() });
      emit('onAgentDone', node);
      break;
    }

    case 'turn_complete':
      emit('onTurnComplete', msg);
      break;

    case 'alert':
      emit('onAlert', msg);
      break;

    default:
      break;   // unknown event types are ignored, never faked
  }
}

function slug(text) {
  return String(text || '')
    .replace(/[^a-zA-Z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .toLowerCase()
    .slice(0, 60);
}

// Close the socket while hidden; reopen on return.
document.addEventListener('visibilitychange', () => {
  if (document.hidden) {
    disconnect();
  } else {
    backoff = 1000;
    connect();
  }
});
