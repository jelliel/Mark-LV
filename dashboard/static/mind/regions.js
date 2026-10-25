/**
 * regions.js — pure math where everything goes. No three.js, no scene.
 *
 * The layout math has no scene dependency and can be reasoned about on its
 * own — that's the point of the split.
 *
 * Layouts, from the living-mind vision:
 *   Memory   — a real force-directed layout, baked ONCE at load
 *   Working  — an even ring with a slight vertical wobble
 *   Agents   — a vertical arc, not a circle
 *   Knowledge— a flat grid, roughly square
 *   Tools    — golden-angle spherical distribution, categories inside,
 *              integrations on a slightly larger shell, phase-offset by π
 */

// ── Region anchors (fixed positions, inside the membrane radius ~26) ─────────

export const ANCHORS = {
  core:      { x:  0,   y:  0,   z:  0,  desc: 'origin — Theologicus' },
  memory:    { x: -11,  y:  4,   z:  1,  desc: 'force-directed memory web' },
  agents:    { x:  9,   y:  1,   z: -2,  desc: 'vertical arc' },
  knowledge: { x: -6,   y: -8,   z:  5,  desc: 'flat grid' },
  tools:     { x:  5,   y: -9,   z: -4,  desc: 'capability ball' },
  working:   { x:  0,   y:  3,   z: -6,  desc: 'recent turns ring' },
};

// ── Layout parameters ────────────────────────────────────────────────────────

export const MEMORY_ITERATIONS = 150;
export const MEMORY_DAMPING    = 0.82;
export const MEMORY_GRAVITY    = 0.012;
export const MEMORY_REPULSION  = 42.0;
export const MEMORY_MIN_DIST   = 1.2;
export const MEMORY_SPREAD     = 7.0;

export const WORKING_RADIUS    = 3.2;
export const WORKING_WOBBLE    = 0.6;

export const AGENT_ARC_RADIUS  = 6.0;
export const AGENT_ARC_SPREAD  = 4.2;

export const TOOLS_INNER_R     = 3.4;
export const TOOLS_OUTER_R     = 4.6;
export const GOLDEN_ANGLE      = Math.PI * (3 - Math.sqrt(5));

// ── Palette (mirrors the backend) ────────────────────────────────────────────

export const COLORS = {
  core:      '#2DD4A8',   // teal
  memory:    '#A78BFA',   // violet
  working:   '#67E8F9',   // cyan
  agents:    '#E88FB3',   // rose
  knowledge: '#F5A524',   // amber
  tools:     '#8B93A1',   // slate
};

export const BACK_BG    = '#05070B';
export const FOG_DENS   = 0.012;
export const MEMBRANE_R = 26;

export const NODE_SIZE = {
  core: 3.0, memory: 1.0, working: 0.9, agents: 1.6, knowledge: 1.4, tools: 0.8,
};

export const EDGE_BASE_OPACITY = 0.18;
export const EDGE_SIMILARITY_OPACITY = 0.20;

// ── Stable hash (FNV-1a) → a float in [0,1) ─────────────────────────────────

export function hashUnit(text) {
  let h = 0x811c9dc5;
  const s = String(text || '');
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = (h * 0x01000193) >>> 0;
  }
  return (h % 100000) / 100000;
}

/** Deterministic unit vector from a string — the same id always lands in the
 *  same place, so a reload doesn't reshuffle the map. */
export function hashVector(id) {
  const a = hashUnit(id) * Math.PI * 2;
  const b = hashUnit(id + '#b') * Math.PI * 2;
  const c = hashUnit(id + '#c') * Math.PI * 2;
  return {
    x: Math.sin(a) * Math.cos(b),
    y: Math.cos(c) * 0.6 + Math.sin(b) * 0.2,
    z: Math.sin(b) * Math.sin(c),
  };
}

// ── Layouts ──────────────────────────────────────────────────────────────────

/**
 * Force-directed layout for the memory web, baked once.
 * node-node repulsion (inverse-square, min-distance clamp so coincident
 * nodes don't explode), spring attraction along each similarity edge scaled
 * by its weight, and a gentle gravity pull toward the anchor. Velocity is
 * damped each step. Seeded from the id hash so it is identical on reload.
 */
function layoutMemory(memoryNodes, similarityEdges, anchor) {
  const n = memoryNodes.length;
  if (!n) return new Map();

  const pos = memoryNodes.map((node) => {
    const v = hashVector(node.id);
    return { x: v.x * MEMORY_SPREAD, y: v.y * MEMORY_SPREAD, z: v.z * MEMORY_SPREAD };
  });
  const vel = memoryNodes.map(() => ({ x: 0, y: 0, z: 0 }));

  // Index the similarity edges by node id.
  const index = new Map(memoryNodes.map((node, i) => [node.id, i]));
  const springs = [];
  for (const e of similarityEdges) {
    const a = index.get(e.source);
    const b = index.get(e.target);
    if (a === undefined || b === undefined) continue;
    springs.push({ a, b, w: e.weight ?? 1.0 });
  }

  for (let step = 0; step < MEMORY_ITERATIONS; step++) {
    // Repulsion.
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        let dx = pos[i].x - pos[j].x;
        let dy = pos[i].y - pos[j].y;
        let dz = pos[i].z - pos[j].z;
        let d2 = dx * dx + dy * dy + dz * dz;
        if (d2 < 1e-6) {
          // Coincident: nudge deterministically instead of exploding.
          const v = hashVector(memoryNodes[i].id + memoryNodes[j].id);
          dx = v.x * 0.01; dy = v.y * 0.01; dz = v.z * 0.01;
          d2 = dx * dx + dy * dy + dz * dz;
        }
        const d = Math.sqrt(d2);
        const clamped = Math.max(d, MEMORY_MIN_DIST);
        const f = MEMORY_REPULSION / (clamped * clamped);
        const ux = dx / d, uy = dy / d, uz = dz / d;
        vel[i].x += ux * f; vel[i].y += uy * f; vel[i].z += uz * f;
        vel[j].x -= ux * f; vel[j].y -= uy * f; vel[j].z -= uz * f;
      }
    }
    // Springs.
    for (const s of springs) {
      const dx = pos[s.b].x - pos[s.a].x;
      const dy = pos[s.b].y - pos[s.a].y;
      const dz = pos[s.b].z - pos[s.a].z;
      const d = Math.sqrt(dx * dx + dy * dy + dz * dz) || 1e-6;
      const f = (d - 2.5) * 0.035 * s.w;
      const ux = dx / d, uy = dy / d, uz = dz / d;
      vel[s.a].x += ux * f; vel[s.a].y += uy * f; vel[s.a].z += uz * f;
      vel[s.b].x -= ux * f; vel[s.b].y -= uy * f; vel[s.b].z -= uz * f;
    }
    // Gravity + integration.
    for (let i = 0; i < n; i++) {
      vel[i].x += (anchor.x - pos[i].x) * MEMORY_GRAVITY;
      vel[i].y += (anchor.y - pos[i].y) * MEMORY_GRAVITY;
      vel[i].z += (anchor.z - pos[i].z) * MEMORY_GRAVITY;
      vel[i].x *= MEMORY_DAMPING;
      vel[i].y *= MEMORY_DAMPING;
      vel[i].z *= MEMORY_DAMPING;
      pos[i].x += vel[i].x;
      pos[i].y += vel[i].y;
      pos[i].z += vel[i].z;
    }
  }

  const out = new Map();
  memoryNodes.forEach((node, i) => out.set(node.id, pos[i]));
  return out;
}

/** Working memory: an even ring with a slight vertical wobble. */
function layoutWorking(nodes, anchor) {
  const out = new Map();
  const n = nodes.length;
  nodes.forEach((node, i) => {
    const angle = (i / Math.max(n, 1)) * Math.PI * 2;
    out.set(node.id, {
      x: anchor.x + Math.cos(angle) * WORKING_RADIUS,
      y: anchor.y + Math.sin(angle * 2) * WORKING_WOBBLE,
      z: anchor.z + Math.sin(angle) * WORKING_RADIUS,
    });
  });
  return out;
}

/** Agents: a vertical arc — distribute along an arc parameter so they read
 *  as a column of presences off to one side, not a circle. */
function layoutAgents(nodes, anchor) {
  const out = new Map();
  const n = nodes.length;
  nodes.forEach((node, i) => {
    const t = n <= 1 ? 0.5 : i / (n - 1);
    const angle = -AGENT_ARC_SPREAD / 2 + t * AGENT_ARC_SPREAD;
    out.set(node.id, {
      x: anchor.x + Math.sin(angle) * AGENT_ARC_RADIUS,
      y: anchor.y + (t - 0.5) * 9.0,
      z: anchor.z + (Math.cos(angle) - 1) * AGENT_ARC_RADIUS * 0.6,
    });
  });
  return out;
}

/** Knowledge: a flat grid, roughly square, centered on its anchor. */
function layoutKnowledge(nodes, anchor) {
  const out = new Map();
  const n = nodes.length;
  const cols = Math.max(1, Math.ceil(Math.sqrt(n)));
  const gap = 2.2;
  nodes.forEach((node, i) => {
    const c = i % cols;
    const r = Math.floor(i / cols);
    const rows = Math.ceil(n / cols);
    out.set(node.id, {
      x: anchor.x + (c - (cols - 1) / 2) * gap,
      y: anchor.y + (r - (rows - 1) / 2) * gap,
      z: anchor.z,
    });
  });
  return out;
}

/** Tools: a compact "capability ball". Tool categories on an inner sphere
 *  using golden-angle spherical distribution; integrations on a slightly
 *  larger shell with the golden-angle phase offset by π, so they interleave
 *  rather than shadow the categories. */
function layoutTools(nodes, anchor) {
  const out = new Map();
  const n = nodes.length;
  const categories = new Set(nodes.map((node) => node.extra?.kind || 'tool'));
  nodes.forEach((node, i) => {
    const isIntegration = node.extra?.kind === 'integration';
    const radius = isIntegration ? TOOLS_OUTER_R : TOOLS_INNER_R;
    const catIndex = categories.size ? [...categories].indexOf(node.extra?.kind || 'tool') : 0;
    const y = n <= 1 ? 0 : 1 - (i / (n - 1)) * 2;
    const r = Math.sqrt(Math.max(0, 1 - y * y));
    const theta = GOLDEN_ANGLE * i + (isIntegration ? Math.PI : 0);
    // Bundle each category's tools tightly around its anchor point.
    const catTheta = GOLDEN_ANGLE * catIndex + (isIntegration ? Math.PI : 0);
    const catY = categories.size <= 1 ? 0 : 1 - (catIndex / (categories.size - 1)) * 2;
    const catR = Math.sqrt(Math.max(0, 1 - catY * catY));
    const catX = Math.cos(catTheta) * catR * radius;
    const catZ = Math.sin(catTheta) * catR * radius;
    const jitter = 0.55;
    out.set(node.id, {
      x: anchor.x + catX + r * Math.cos(theta) * jitter,
      y: anchor.y + catY * radius + y * jitter,
      z: anchor.z + catZ + r * Math.sin(theta) * jitter,
    });
  });
  return out;
}

/**
 * Lay out every node. Returns a Map id → {x, y, z}.
 * Pure math — no three.js anywhere in this file.
 */
export function layoutNodes(nodes, edges) {
  const positions = new Map();
  const byRegion = new Map();
  for (const node of nodes) {
    if (!byRegion.has(node.region)) byRegion.set(node.region, []);
    byRegion.get(node.region).push(node);
  }

  const core = byRegion.get('core');
  if (core) {
    for (const node of core) positions.set(node.id, { x: 0, y: 0, z: 0 });
  }

  const memory = byRegion.get('memory') || [];
  const similarityEdges = (edges || []).filter((e) => e.kind === 'similarity');
  for (const [id, p] of layoutMemory(memory, similarityEdges, ANCHORS.memory)) {
    positions.set(id, { x: ANCHORS.memory.x + p.x, y: ANCHORS.memory.y + p.y, z: ANCHORS.memory.z + p.z });
  }

  for (const [id, p] of layoutWorking(byRegion.get('working') || [], ANCHORS.working)) {
    positions.set(id, p);
  }
  for (const [id, p] of layoutAgents(byRegion.get('agents') || [], ANCHORS.agents)) {
    positions.set(id, p);
  }
  for (const [id, p] of layoutKnowledge(byRegion.get('knowledge') || [], ANCHORS.knowledge)) {
    positions.set(id, p);
  }
  for (const [id, p] of layoutTools(byRegion.get('tools') || [], ANCHORS.tools)) {
    positions.set(id, p);
  }

  // Any region we don't know about still gets a deterministic place, so a
  // node is never invisible and never lands on top of another.
  for (const [region, regionNodes] of byRegion) {
    if (positions.has(regionNodes[0]?.id) && regionNodes.every((n) => positions.has(n.id))) continue;
    const anchor = ANCHORS[region] || { x: 0, y: 0, z: 0 };
    regionNodes.forEach((node, i) => {
      if (positions.has(node.id)) return;
      const v = hashVector(node.id);
      positions.set(node.id, {
        x: anchor.x + v.x * 5,
        y: anchor.y + v.y * 5,
        z: anchor.z + v.z * 5,
      });
    });
  }

  return positions;
}
