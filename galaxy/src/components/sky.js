import * as THREE from 'three';

export function createSky(scene: THREE.Scene) {
  // Create a large plane for the sky background
  const geometry = new THREE.PlaneGeometry(1000, 1000);
  const material = new THREE.ShaderMaterial({
    uniforms: {
      time: { value: 0 },
      resolution: { value: new THREE.Vector2() },
      orbColor: { value: new THREE.Color(0x00d4ff) }
    },
    vertexShader: `
      varying vec2 vUv;
      void main() {
        vUv = uv;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: `
      varying vec2 vUv;
      uniform float time;
      uniform vec2 resolution;
      uniform vec3 orbColor;

      // Fractal noise function
      float noise(vec2 p) {
        vec2 i = floor(p);
        vec2 f = fract(p);
        f = f * f * (3.0 - 2.0 * f);

        float n = i.x + i.y * 57.0;
        float a = random(n + 0.0);
        float b = random(n + 1.0);
        float c = random(n + 2.0);
        float d = random(n + 3.0);

        return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
      }

      float random(float x) {
        return fract(sin(x) * 10000.0);
      }

      void main() {
        vec2 uv = vUv * 2.0 - 1.0;
        uv.x *= resolution.x / resolution.y;

        // Deep space base: near-black navy, slightly darker toward edges
        float depth = 1.0 - smoothstep(0.2, 1.0, length(uv));
        vec3 color = vec3(0.0, 0.02, 0.06) * depth; // Navy blue

        // Three nebula layers from fractal value noise
        vec2 nebulaUV = uv * 0.5 + time * 0.01;

        // Teal-green nebula
        float nebula1 = noise(nebulaUV * 0.5);
        nebula1 = smoothstep(0.4, 0.6, nebula1);
        color += vec3(0.0, 0.3, 0.2) * nebula1 * 0.3;

        // Purple nebula
        float nebula2 = noise(nebulaUV * 0.3 + vec2(10.0, 20.0));
        nebula2 = smoothstep(0.3, 0.5, nebula2);
        color += vec3(0.4, 0.0, 0.3) * nebula2 * 0.2;

        // Blue nebula
        float nebula3 = noise(nebulaUV * 0.4 + vec2(30.0, 10.0));
        nebula3 = smoothstep(0.35, 0.55, nebula3);
        color += vec3(0.0, 0.2, 0.4) * nebula3 * 0.2;

        // Orb-coloured bloom behind centre
        float bloom = smoothstep(0.8, 0.9, length(uv));
        vec3 bloomColor = orbColor * 0.7;
        color += bloomColor * bloom * 0.4;

        // Two star layers
        // Fine field of pinpoint stars
        float fineStars = random(uv.x * 1000.0 + time * 0.1) * random(uv.y * 1000.0 + time * 0.1);
        fineStars = step(0.995, fineStars); // Very sparse
        color += vec3(0.8, 0.9, 1.0) * fineStars * 0.3;

        // Sparse layer of larger soft stars
        vec2 starUV = uv * 5.0 + time * 0.05;
        float softStars = random(floor(starUV.x), floor(starUV.y));
        softStars = smoothstep(0.95, 0.98, softStars);
        color += vec3(0.9, 0.9, 1.0) * softStars * 0.2;

        // Make star grid square in screen space
        // Aspect ratio compensation handled by passing resolution to shader

        // Gentle vignette
        float vignette = smoothstep(0.8, 1.0, length(uv));
        color *= vignette;

        gl_FragColor = vec4(color, 1.0);
      }
    `,
    transparent: true,
    depthWrite: false
  });

  const sky = new THREE.Mesh(geometry, material);
  sky.rotation.x = -Math.PI / 2; // Make it horizontal
  scene.add(sky);

  // Store reference to material for updates
  sky.material.needsUpdate = true;

  return {
    update: (delta: number, state: string, levels: { voice: number, bass: number, treble: number }) => {
      const material = sky.material as THREE.ShaderMaterial;
      material.uniforms.time.value += delta;

      // Update resolution uniform
      material.uniforms.resolution.value.set(
        window.innerWidth,
        window.innerHeight
      );

      // Update orb color for bloom effect
      const stateColors: Record<string, number> = {
        idle: 0x00d4ff,
        arming: 0xff6b00,
        listening: 0xffcc00,
        thinking: 0x800080, // Purple-blue mix
        speaking: 0x00d4ff,
        error: 0xff3355
      };

      const color = stateColors[state] || stateColors.idle;
      material.uniforms.orbColor.value.setHex(color);

      // Increase bloom intensity when speaking
      const bloomIntensity = state === 'speaking' || state === 'thinking' ? 1.5 : 1.0;
      // This would require modifying the shader - for now we'll note it
    }
  };
}