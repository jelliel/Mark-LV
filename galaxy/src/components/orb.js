import * as THREE from 'three';
import { SimplexNoise } from 'simplex-noise';

export function createOrb(scene: THREE.Scene) {
  // Create orb geometry - wireframe icosahedron
  const geometry = new THREE.IcosahedronGeometry(1, 2); // Radius 1, detail about 24
  const material = new THREE.MeshBasicMaterial({
    color: 0x00d4ff, // Default teal
    wireframe: true,
    transparent: true,
    opacity: 0.8
  });

  const orb = new THREE.Mesh(geometry, material);
  scene.add(orb);

  // Store original vertices for displacement
  const originalPositions = geometry.attributes.position.array.slice();

  // Noise generators for different octaves
  const noiseLow = new SimplexNoise();
  const noiseMedium = new SimplexNoise();
  const noiseHigh = new SimplexNoise();

  // State management
  let currentState = 'idle';
  let audioLevels = { voice: 0, bass: 0, treble: 0 };

  // Orb properties based on state
  const stateConfigs = {
    idle: {
      color: 0x00d4ff, // teal
      breathing: 0.04, // slow sine
      glowIntensity: 0.3,
      noiseSpeed: 0.5,
      displacementAmplitude: 0.0
    },
    arming: {
      color: 0xff6b00, // ember
      breathing: 0.0,
      glowIntensity: 0.1,
      noiseSpeed: 0.3,
      displacementAmplitude: 0.0
    },
    listening: {
      color: 0xffcc00, // gold
      breathing: 0.0,
      glowIntensity: 0.8,
      noiseSpeed: 0.7,
      displacementAmplitude: 0.0
    },
    thinking: {
      color: 0x00d4ff, // starts teal, shifts to purple
      breathing: 0.0,
      glowIntensity: 0.5,
      noiseSpeed: 0.9,
      displacementAmplitude: 0.0,
      pulse: 0.0
    },
    speaking: {
      color: 0x00d4ff, // teal
      breathing: 0.0,
      glowIntensity: 0.9,
      noiseSpeed: 1.0,
      displacementAmplitude: 0.0
    },
    error: {
      color: 0xff3355, // red
      breathing: 0.0,
      glowIntensity: 0.0,
      noiseSpeed: 0.0,
      displacementAmplitude: 0.0
    }
  };

  // Time-based values for animation
  let time = 0;

  return {
    update: (delta: number, state: string, levels: { voice: number, bass: number, treble: number }) => {
      time += delta;
      currentState = state;
      audioLevels = levels;

      const config = stateConfigs[state as keyof typeof stateConfigs] || stateConfigs.idle;

      // Update material color
      material.color.setHex(config.color);

      // Calculate breathing effect (slow sine wave)
      const breathing = Math.sin(time * 0.7) * config.breathing;

      // Calculate audio-based displacement
      const voiceLevel = levels.voice;
      const bassLevel = levels.bass;

      // Audio displacement: voice × 0.55 + bass × 0.35
      const audioDisplacement = (voiceLevel * 0.55 + bassLevel * 0.35) * 0.45;

      // Apply vertex displacement using 3-octave simplex noise
      const positions = geometry.attributes.position.array;
      for (let i = 0; i < positions.length; i += 3) {
        // Original position
        const x = originalPositions[i];
        const y = originalPositions[i + 1];
        const z = originalPositions[i + 2];

        // Normalize to get direction from center
        const length = Math.sqrt(x * x + y * y + z * z);
        const nx = x / length;
        const ny = y / length;
        const nz = z / length;

        // Sample noise at different frequencies
        const noiseLowVal = noiseLow.noise3D(
          nx * 0.5 + time * config.noiseSpeed,
          ny * 0.5 + time * config.noiseSpeed,
          nz * 0.5 + time * config.noiseSpeed
        ) * 0.5;

        const noiseMediumVal = noiseMedium.noise3D(
          nx * 1.5 + time * config.noiseSpeed * 2,
          ny * 1.5 + time * config.noiseSpeed * 2,
          nz * 1.5 + time * config.noiseSpeed * 2
        ) * 0.3;

        const noiseHighVal = noiseHigh.noise3D(
          nx * 3.0 + time * config.noiseSpeed * 4 + voiceLevel * 10, // High octave only with audio
          ny * 3.0 + time * config.noiseSpeed * 4 + voiceLevel * 10,
          nz * 3.0 + time * config.noiseSpeed * 4 + voiceLevel * 10
        ) * 0.2 * voiceLevel; // High octave modulated by audio

        // Combine noise sources
        let displacement = noiseLowVal + noiseMediumVal + noiseHighVal;

        // Add breathing effect
        displacement += breathing;

        // Add audio displacement
        displacement += audioDisplacement;

        // Clamp to ±0.45 as specified
        displacement = Math.max(-0.45, Math.min(0.45, displacement));

        // Apply displacement along normal
        positions[i] = x + nx * displacement;
        positions[i + 1] = y + ny * displacement;
        positions[i + 2] = z + nz * displacement;
      }

      // Mark geometry attributes as needing update
      geometry.attributes.position.needsUpdate = true;

      // Update glow intensity (material opacity)
      material.opacity = 0.6 + config.glowIntensity * 0.4; // Base 0.6 + glow effect

      // Special thinking state pulse
      if (state === 'thinking') {
        // Slow pulse for thinking state
        const pulse = Math.sin(time * 2) * 0.2 + 0.8;
        material.opacity *= pulse;
      }

      // Scale adjustment based on voice and bass (minor effect)
      const scale = 1.0 + (levels.voice * 0.1 + levels.bass * 0.05);
      orb.scale.set(scale, scale, scale);

      // Slow rotation
      orb.rotation.y += time * 0.1;
      orb.rotation.x += time * 0.05;
    }
  };
}