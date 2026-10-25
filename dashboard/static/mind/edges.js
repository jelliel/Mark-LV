/**
 * edges.js — connections that arc instead of slicing.
 *
 * Every edge is a QuadraticBezierCurve3 whose control point is the midpoint
 * pushed ~12% of the chord length along a perpendicular. Straight lines slice
 * through clusters and make the scene look like a wireframe; arcs make it
 * look anatomical.
 *
 * All edges of the same kind are merged into ONE LineSegments — the
 * difference between 400 draw calls and 6.
 *
 * Two shader treatments:
 *  - similarity shimmer: per-vertex aPhase, alpha breathes on a sine
 *  - energy-flow trunks: a comet head travels along the curve, tail decays
 *    exponentially. The sign of uSpeed sets the direction — positive streams
 *    outward from the core, negative streams inward (recall flows memory→core).
 */

import * as THREE from 'three';
import { uTime } from './nodes.js';

export const EDGE_COLORS = {
  similarity: '#A78BFA',
  trunk:      '#67E8F9',
  recall:     '#8B93A1',
};

const SHIMMER_VERT = /* glsl */`
  attribute float aPhase;
  varying float vPhase;
  void main() {
    vPhase = aPhase;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const SHIMMER_FRAG = /* glsl */`
  varying float vPhase;
  uniform vec3 uColor;
  uniform float uBaseOpacity;
  uniform float uShimmer;
  uniform float uTime;
  void main() {
    float breath = 0.75 + 0.25 * sin(uTime * 1.6 + vPhase);
    gl_FragColor = vec4(uColor, uBaseOpacity * breath * uShimmer);
  }
`;

const FLOW_VERT = /* glsl */`
  attribute float aT;        // position along the curve, 0→1
  attribute float aPhase;
  attribute float aWeight;
  varying float vT;
  varying float vPhase;
  varying float vWeight;
  void main() {
    vT = aT; vPhase = aPhase; vWeight = aWeight;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const FLOW_FRAG = /* glsl */`
  varying float vT;
  varying float vPhase;
  varying float vWeight;
  uniform vec3 uColor;
  uniform float uBaseOpacity;
  uniform float uFlow;
  uniform float uTime;
  uniform float uSpeed;
  void main() {
    // The comet head, and a distance behind it.
    float head = fract(uTime * uSpeed + vPhase);
    float d = fract(head - vT);
    float tail = exp(-d * 9.0);
    vec3 color = uColor * (0.5 + 0.5 * vWeight) + vec3(1.0) * tail * 0.8;
    float alpha = (uBaseOpacity * 0.5 + tail * 0.7) * uWeight * uFlow;
    gl_FragColor = vec4(color, alpha);
  }
`;

/** Stable hash → a phase in [0,1). */
function phaseOf(key) {
  let h = 0x811c9dc5;
  for (let i = 0; i < key.length; i++) {
    h ^= key.charCodeAt(i);
    h = (h * 0x01000193) >>> 0;
  }
  return (h % 10000) / 10000;
}

/**
 * Build the arc for one edge.
 * The control point is the midpoint pushed along a perpendicular: the chord
 * crossed with the outward-from-origin direction.
 */
function arcBetween(a, b) {
  const mid = a.clone().add(b).multiplyScalar(0.5);
  const chord = b.clone().sub(a);
  const outward = mid.clone().normalize();
  const perp = chord.clone().cross(outward);
  if (perp.lengthSq() < 1e-6) {
    // Degenerate — chord is parallel to the outward direction. Pick any
    // perpendicular.
    perp.set(0, 1, 0).cross(chord);
  }
  perp.normalize().multiplyScalar(chord.length() * 0.12);
  const ctrl = mid.add(perp);
  return new THREE.QuadraticBezierCurve3(a.clone(), ctrl, b.clone());
}

/**
 * Build all the edges. Returns a group plus a lookup of the static curves,
 * so the pulse system can travel along them.
 */
export function buildEdges(edges, positionsById, colorsByRegion) {
  const group = new THREE.Group();
  const byKind = new Map();     // kind → { keys, curves, weights }
  const curveLookup = new Map(); // "source|target" → curve (either direction)

  for (const e of edges) {
    const a = positionsById.get(e.source);
    const b = positionsById.get(e.target);
    if (!a || !b) continue;      // no fake edges between nodes that don't exist
    const curve = arcBetween(a, b);
    const key = `${e.source}|${e.target}`;
    const rkey = `${e.target}|${e.source}`;
    if (!curveLookup.has(key)) curveLookup.set(key, curve);
    if (!curveLookup.has(rkey)) curveLookup.set(rkey, curve);
    if (!byKind.has(e.kind)) byKind.set(e.kind, { keys: [], curves: [], weights: [] });
    const bucket = byKind.get(e.kind);
    bucket.keys.push(key);
    bucket.curves.push(curve);
    bucket.weights.push(e.weight ?? 1.0);
  }

  const SEGMENTS = 24;
  const materials = [];

  for (const [kind, bucket] of byKind) {
    const count = bucket.curves.length;
    if (!count) continue;

    const positions = new Float32Array(count * SEGMENTS * 2 * 3);
    const phases = new Float32Array(count * SEGMENTS * 2);
    const ts = new Float32Array(count * SEGMENTS * 2);
    const weights = new Float32Array(count * SEGMENTS * 2);

    const color = EDGE_COLORS[kind] || '#8B93A1';
    const isTrunk = kind === 'trunk' || kind === 'recall';

    let p = 0, ph = 0, tt = 0, w = 0;
    for (let i = 0; i < count; i++) {
      const curve = bucket.curves[i];
      const pts = curve.getPoints(SEGMENTS);
      const phase = phaseOf(bucket.keys[i]);
      const weight = bucket.weights[i];
      for (let s = 0; s < SEGMENTS; s++) {
        for (const pt of [pts[s], pts[s + 1]]) {
          positions[p++] = pt.x; positions[p++] = pt.y; positions[p++] = pt.z;
          phases[ph++] = phase;
          ts[tt++] = s / SEGMENTS;
          weights[w++] = weight;
        }
      }
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));

    let mat;
    if (isTrunk) {
      geo.setAttribute('aT', new THREE.BufferAttribute(ts, 1));
      geo.setAttribute('aPhase', new THREE.BufferAttribute(phases, 1));
      geo.setAttribute('aWeight', new THREE.BufferAttribute(weights, 1));
      mat = new THREE.ShaderMaterial({
        vertexShader: FLOW_VERT,
        fragmentShader: FLOW_FRAG,
        uniforms: {
          uTime,
          uColor: { value: new THREE.Color(color) },
          uBaseOpacity: { value: 0.18 },
          uFlow: { value: 1.0 },
          // Recall flows memory→core (inward = negative); trunks flow outward.
          uSpeed: { value: kind === 'recall' ? -0.35 : 0.30 },
        },
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      });
      // ShaderMaterial ignores .opacity — route it into the uniform so the
      // hover code doesn't have to special-case these materials.
      Object.defineProperty(mat, 'opacity', {
        get() { return this.uniforms.uBaseOpacity.value; },
        set(v) { this.uniforms.uBaseOpacity.value = v; },
      });
    } else {
      geo.setAttribute('aPhase', new THREE.BufferAttribute(phases, 1));
      mat = new THREE.ShaderMaterial({
        vertexShader: SHIMMER_VERT,
        fragmentShader: SHIMMER_FRAG,
        uniforms: {
          uTime,
          uColor: { value: new THREE.Color(color) },
          uBaseOpacity: { value: 0.20 },
          uShimmer: { value: 1.0 },
        },
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      });
      Object.defineProperty(mat, 'opacity', {
        get() { return this.uniforms.uBaseOpacity.value; },
        set(v) { this.uniforms.uBaseOpacity.value = v; },
      });
    }

    const lines = new THREE.LineSegments(geo, mat);
    lines.renderOrder = -2;
    group.add(lines);
    materials.push(mat);
  }

  return { group, curveLookup, materials };
}
