/**
 * nodes.js — the node look. This is where the map stops being a graph
 * viewer and starts being a light source.
 *
 * Every node is a reverse-fresnel glow sphere: a white-hot core bleeding
 * into a coloured halo. Small nodes (memories, tools, threads, knowledge
 * files) go into ONE InstancedMesh per region — per region, not one global,
 * so the legend can toggle a whole region by flipping one group's visibility.
 *
 * The core (Theologicus) is a layered sun built by hand: white-hot inner
 * sphere, glow shell, two counter-rotating corona billboards, two torus
 * rings for the prompt blocks (spun about Y — a torus's symmetry axis is Z,
 * so rotating about Z is invisible).
 */

import * as THREE from 'three';

// One shared time uniform, written once per frame.
export const uTime = { value: 0 };

const GLOW_VERT = /* glsl */`
  attribute float aPhase;
  attribute float aFreshness;
  varying vec3 vNormal;
  varying vec3 vViewDir;
  varying float vFreshness;
  uniform float uTime;
  void main() {
    vFreshness = aFreshness;
    // Breathing: frequency AND offset vary per node, so the field shimmers
    // organically instead of pulsing in unison.
    float f = 3.5 + 2.5 * fract(aPhase * 0.7);
    float breathe = 1.0 + 0.06 * sin(uTime * f + aPhase);
    // Fresh memories burn; stale ones ember.
    breathe *= 0.6 + 0.4 * aFreshness;
    vec3 pos = position * breathe;
    vec4 mv = modelViewMatrix * instanceMatrix * vec4(pos, 1.0);
    vNormal = normalize(normalMatrix * mat3(instanceMatrix) * normal);
    vViewDir = normalize(-mv.xyz);
    gl_Position = projectionMatrix * mv;
  }
`;

const GLOW_FRAG = /* glsl */`
  varying vec3 vNormal;
  varying vec3 vViewDir;
  varying float vFreshness;
  uniform vec3 uColor;
  uniform float uOpacity;
  void main() {
    float facing = max(dot(normalize(vNormal), normalize(vViewDir)), 0.0);
    float core = pow(facing, 2.5);          // hot centre
    float rim  = pow(1.0 - facing, 2.0);    // coloured edge
    vec3 color = mix(uColor, vec3(1.0), core * 0.85)
               + uColor * rim * 1.4;
    // Fresh nodes burn brighter.
    color *= 0.45 + 0.75 * vFreshness;
    float alpha = (core * 0.95 + rim * 0.6) * uOpacity;
    gl_FragColor = vec4(color, alpha);
  }
`;

/** Billboarded instanced quad — the soft aura around a node.
 *  Two triangles instead of hundreds; analytic radial falloff, so the
 *  falloff is genuinely soft instead of a hard-edged disk leaning on bloom
 *  to hide it. Shares instanceMatrix/instanceColor with the node mesh, so
 *  any scale animation moves both layers in lockstep for free. */
const AURA_VERT = /* glsl */`
  attribute float aPhase;
  attribute float aFreshness;
  varying vec2 vUv;
  varying float vFreshness;
  uniform float uTime;
  void main() {
    vUv = uv;
    vFreshness = aFreshness;
    float f = 3.5 + 2.5 * fract(aPhase * 0.7);
    float breathe = 1.0 + 0.06 * sin(uTime * f + aPhase);
    vec4 center = modelViewMatrix * instanceMatrix * vec4(0.0, 0.0, 0.0, 1.0);
    float scale = length(vec3(instanceMatrix[0].xyz)) * 3.2 * breathe;
    center.xy += position.xy * scale;
    gl_Position = projectionMatrix * center;
  }
`;

const AURA_FRAG = /* glsl */`
  varying vec2 vUv;
  varying float vFreshness;
  uniform vec3 uColor;
  uniform float uOpacity;
  void main() {
    float d = length(vUv - 0.5) * 2.0;
    if (d > 1.0) discard;
    float fall = pow(max(1.0 - d, 0.0), 2.2);
    vec3 color = uColor * (0.5 + 0.5 * vFreshness);
    gl_FragColor = vec4(color, fall * uOpacity * 0.6);
  }
`;

/** FNV-1a over the id — stable across reloads, unlike Math.random(). */
export function hashId(id) {
  let h = 0x811c9dc5;
  for (let i = 0; i < id.length; i++) {
    h ^= id.charCodeAt(i);
    h = (h * 0x01000193) >>> 0;
  }
  return (h % 100000) / 100000;
}

/** A radial-gradient CanvasTexture, generated once and reused everywhere. */
export function radialTexture(inner = 'rgba(255,255,255,1)', outer = 'rgba(255,255,255,0)') {
  const size = 128;
  const c = document.createElement('canvas');
  c.width = c.height = size;
  const ctx = c.getContext('2d');
  const g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  g.addColorStop(0, inner);
  g.addColorStop(0.4, inner.replace(/[\d.]+\)$/, '0.55)'));
  g.addColorStop(1, outer);
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, size, size);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

/**
 * Build the instanced meshes for one region.
 * @param {Array} nodes   the region's nodes
 * @param {string} color  the region's hex colour
 * @param {THREE.Vector3[]} positions  baked layout positions
 */
export function buildRegionMeshes(nodes, color, positions) {
  const count = nodes.length;
  if (!count) return null;

  const group = new THREE.Group();

  const phases = new Float32Array(count);
  const fresh = new Float32Array(count);
  for (let i = 0; i < count; i++) {
    phases[i] = hashId(nodes[i].id) * Math.PI * 2;
    fresh[i] = nodes[i].freshness ?? 1.0;
  }

  // ── the node cores ────────────────────────────────────────────────────────
  const geo = new THREE.SphereGeometry(1, 24, 16);   // an icosahedron reads faceted
  const mat = new THREE.ShaderMaterial({
    vertexShader: GLOW_VERT,
    fragmentShader: GLOW_FRAG,
    uniforms: {
      uTime,
      uColor: { value: new THREE.Color(color) },
      uOpacity: { value: 1.0 },
    },
    transparent: true,
    depthWrite: false,
  });
  const mesh = new THREE.InstancedMesh(geo, mat, count);
  mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  geo.setAttribute('aPhase', new THREE.InstancedBufferAttribute(phases, 1));
  geo.setAttribute('aFreshness', new THREE.InstancedBufferAttribute(fresh, 1));

  const m = new THREE.Matrix4();
  for (let i = 0; i < count; i++) {
    const s = nodes[i].size ?? 1;
    m.makeScale(s, s, s).setPosition(positions[i]);
    mesh.setMatrixAt(i, m);
  }
  mesh.instanceMatrix.needsUpdate = true;
  mesh.userData.ids = nodes.map((n) => n.id);
  mesh.userData.nodes = nodes;
  group.add(mesh);

  // ── the aura ──────────────────────────────────────────────────────────────
  const auraGeo = new THREE.PlaneGeometry(1, 1);
  const auraMat = new THREE.ShaderMaterial({
    vertexShader: AURA_VERT,
    fragmentShader: AURA_FRAG,
    uniforms: {
      uTime,
      uColor: { value: new THREE.Color(color) },
      uOpacity: { value: 1.0 },
    },
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });
  const aura = new THREE.InstancedMesh(auraGeo, auraMat, count);
  auraGeo.setAttribute('aPhase', new THREE.InstancedBufferAttribute(phases, 1));
  auraGeo.setAttribute('aFreshness', new THREE.InstancedBufferAttribute(fresh, 1));
  for (let i = 0; i < count; i++) aura.setMatrixAt(i, mesh.getMatrixAt(i, new THREE.Matrix4()));
  aura.instanceMatrix.needsUpdate = true;
  // The quads expand in the shader, so the CPU-side bounds are wrong.
  aura.frustumCulled = false;
  aura.renderOrder = -1;   // under the cores
  aura.userData.ids = nodes.map((n) => n.id);
  group.add(aura);

  return { group, mesh, aura };
}

/**
 * The core star: a layered sun. White-hot inner sphere with additive
 * blending, the glow shell, two counter-rotating corona billboards, and two
 * torus rings representing the prompt blocks (stable and dynamic).
 */
export function buildCore(color = '#2DD4A8') {
  const group = new THREE.Group();
  const nucleus = new THREE.Group();   // everything breathes together
  group.add(nucleus);

  const tex = radialTexture('rgba(255,255,255,1)', 'rgba(255,255,255,0)');

  // White-hot inner sphere.
  const inner = new THREE.Mesh(
    new THREE.SphereGeometry(1.1, 32, 24),
    new THREE.MeshBasicMaterial({
      color: 0xffffff, transparent: true, opacity: 0.95,
      blending: THREE.AdditiveBlending, depthWrite: false,
    })
  );
  nucleus.add(inner);

  // Glow shell — the reverse-fresnel recipe, hand-built (not instanced).
  const shell = new THREE.Mesh(
    new THREE.SphereGeometry(1.6, 32, 24),
    new THREE.ShaderMaterial({
      vertexShader: /* glsl */`
        varying vec3 vN; varying vec3 vV;
        void main() {
          vec4 mv = modelViewMatrix * vec4(position, 1.0);
          vN = normalize(normalMatrix * normal);
          vV = normalize(-mv.xyz);
          gl_Position = projectionMatrix * mv;
        }`,
      fragmentShader: /* glsl */`
        varying vec3 vN; varying vec3 vV;
        uniform vec3 uColor; uniform float uOpacity;
        void main() {
          float facing = max(dot(normalize(vN), normalize(vV)), 0.0);
          float core = pow(facing, 2.5);
          float rim = pow(1.0 - facing, 2.0);
          vec3 color = mix(uColor, vec3(1.0), core * 0.85) + uColor * rim * 1.4;
          gl_FragColor = vec4(color, (core * 0.95 + rim * 0.6) * uOpacity);
        }`,
      uniforms: {
        uColor: { value: new THREE.Color(color) },
        uOpacity: { value: 1.0 },
      },
      transparent: true, depthWrite: false,
    })
  );
  nucleus.add(shell);

  // Two counter-rotating corona billboards.
  const coronaTight = new THREE.Sprite(new THREE.SpriteMaterial({
    map: tex, color: new THREE.Color(color), transparent: true, opacity: 0.55,
    blending: THREE.AdditiveBlending, depthWrite: false,
  }));
  coronaTight.scale.setScalar(7);
  nucleus.add(coronaTight);

  const coronaWide = new THREE.Sprite(new THREE.SpriteMaterial({
    map: tex, color: new THREE.Color(color), transparent: true, opacity: 0.22,
    blending: THREE.AdditiveBlending, depthWrite: false,
  }));
  coronaWide.scale.setScalar(14);
  nucleus.add(coronaWide);

  // Two torus rings for the prompt blocks. Spin about Y — a torus's symmetry
  // axis is Z, so rotating about Z is invisible.
  const ringStable = new THREE.Mesh(
    new THREE.TorusGeometry(2.6, 0.03, 8, 96),
    new THREE.MeshBasicMaterial({
      color: new THREE.Color(color), transparent: true, opacity: 0.35,
      blending: THREE.AdditiveBlending, depthWrite: false,
    })
  );
  ringStable.rotation.x = Math.PI / 2;
  nucleus.add(ringStable);

  const ringDynamic = new THREE.Mesh(
    new THREE.TorusGeometry(3.4, 0.02, 8, 96),
    new THREE.MeshBasicMaterial({
      color: new THREE.Color(color), transparent: true, opacity: 0.22,
      blending: THREE.AdditiveBlending, depthWrite: false,
    })
  );
  ringDynamic.rotation.x = Math.PI / 2 + 0.4;
  nucleus.add(ringDynamic);

  return {
    group, nucleus, shell, inner,
    coronaTight, coronaWide, ringStable, ringDynamic,
    update(t, flare = 0) {
      // The core breathes; a turn-complete flare swells it and the ring
      // together, on the same envelope, so star and ring flare as one organism.
      const breath = 1 + 0.05 * Math.sin(t * 1.4);
      const swell = 1 + flare * 0.55;
      const s = breath * swell;
      nucleus.scale.setScalar(s);
      inner.scale.setScalar(s);
      shell.scale.setScalar(s);
      coronaTight.material.opacity = 0.55 + flare * 0.4;
      coronaWide.material.opacity = 0.22 + flare * 0.25;
      ringDynamic.material.opacity = 0.22 + flare * 0.7;
      coronaTight.material.rotation = t * 0.15;
      coronaWide.material.rotation = -t * 0.09;
      ringStable.rotation.z = t * 0.2;
      ringDynamic.rotation.z = -t * 0.13;
    },
  };
}

/**
 * An agent's glow sphere — bigger, in its own accent colour, with a
 * circular avatar sprite above it if there is one.
 */
export function buildAgentNode(color, avatarUrl) {
  const group = new THREE.Group();
  const glow = new THREE.Mesh(
    new THREE.SphereGeometry(0.9, 24, 16),
    new THREE.MeshBasicMaterial({
      color: new THREE.Color(color), transparent: true, opacity: 0.85,
      blending: THREE.AdditiveBlending, depthWrite: false,
    })
  );
  group.add(glow);

  if (avatarUrl) {
    const spriteMat = new THREE.SpriteMaterial({
      transparent: true, depthWrite: false,
    });
    const sprite = new THREE.Sprite(spriteMat);
    sprite.scale.setScalar(1.2);
    sprite.position.y = 1.5;
    // On image error, silently keep the glow sphere.
    spriteMat.map = new THREE.TextureLoader().load(avatarUrl, undefined, () => {
      sprite.visible = false;
    });
    group.add(sprite);
  }
  return group;
}
