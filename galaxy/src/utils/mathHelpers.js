/**
 * Frame-rate independent easing function
 * Returns the fraction of remaining distance to cover based on time passed
 * @param fraction Fraction of remaining distance to cover per unit time (0-1)
 * @param deltaTime Time passed since last update
 * @returns Amount to move toward target
 */
export function easeFraction(fraction: number, deltaTime: number): number {
  return 1.0 - Math.pow(1.0 - fraction, deltaTime * 60); // Assuming 60 FPS base
}

/**
 * Smooth step function for interpolation
 * @param edge0 Lower bound
 * @param edge1 Upper bound
 * @param x Value to interpolate
 * @returns Smoothed value between 0 and 1
 */
export function smoothstep(edge0: number, edge1: number, x: number): number {
  const t = Math.max(0, Math.min(1, (x - edge0) / (edge1 - edge0)));
  return t * t * (3 - 2 * t);
}

/**
 * Linear interpolation
 * @param start Start value
 * @param end End value
 * @param t Interpolation factor (0-1)
 * @returns Interpolated value
 */
export function lerp(start: number, end: number, t: number): number {
  return start + (end - start) * t;
}

/**
 * Clamp value between min and max
 * @param value Value to clamp
 * @param min Minimum value
 * @param max Maximum value
 * @returns Clamped value
 */
export function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

/**
 * Convert frequency band to level (0-1 range)
 * @param bins Array of frequency bin values (0-1)
 * @param startBin Starting bin index (inclusive)
 * @param endBin Ending bin index (exclusive)
 * @returns Average level of the frequency band
 */
export function getFrequencyBandLevel(bins: number[], startBin: number, endBin: number): number {
  if (bins.length === 0 || startBin >= endBin) return 0;

  let sum = 0;
  let count = 0;

  for (let i = startBin; i < Math.min(endBin, bins.length); i++) {
    sum += bins[i];
    count++;
  }

  return count > 0 ? sum / count : 0;
}

/**
 * Generate deterministic synthetic envelope that looks like speech
 * @param time Current time in seconds
 * @returns Object with voice, bass, treble levels
 */
export function getSyntheticSpeechEnvelope(time: number): { voice: number, bass: number, treble: number } {
  // Create a speech-like pattern with formants and bursts
  const phraseTime = time % 5; // 5-second phrases

  // Voice envelope: slow onset, sustained, quick release
  let voice = 0;
  if (phraseTime < 0.1) {
    voice = phraseTime / 0.1; // Attack
  } else if (phraseTime < 4.0) {
    voice = 0.7 + Math.sin(phraseTime * 10) * 0.2; // Sustain with slight variation
  } else if (phraseTime < 4.2) {
    voice = 0.7 * (1.0 - (phraseTime - 4.0) / 0.2); // Release
  }

  // Bass: follows voice with slight delay
  const bassTime = phraseTime - 0.05;
  let bass = 0;
  if (bassTime > 0 && bassTime < 4.0) {
    bass = 0.5 + Math.sin(bassTime * 15) * 0.3;
  }

  // Treble: higher frequency content
  const trebleTime = phraseTime + 0.1;
  let treble = 0;
  if (trebleTime > 0 && trebleTime < 4.0) {
    treble = 0.4 + Math.sin(trebleTime * 20) * 0.2;
  }

  return {
    voice: Math.max(0, Math.min(1, voice)),
    bass: Math.max(0, Math.min(1, bass)),
    treble: Math.max(0, Math.min(1, treble))
  };
}