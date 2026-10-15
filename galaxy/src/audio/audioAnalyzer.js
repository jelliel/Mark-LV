export class AudioAnalyzer {
  private voiceLevel: number = 0;
  private bassLevel: number = 0;
  private trebleLevel: number = 0;

  constructor() {
    // Initialize with silence
  }

  setLevels(levels: { voice: number, bass: number, treble: number }): void {
    this.voiceLevel = levels.voice;
    this.bassLevel = levels.bass;
    this.trebleLevel = levels.treble;
  }

  getLevels(): { voice: number, bass: number, treble: number } {
    return {
      voice: this.voiceLevel,
      bass: this.bassLevel,
      treble: this.trebleLevel
    };
  }

  // For demo/synthetic audio when no real audio is available
  getSyntheticLevels(): { voice: number, bass: number, treble: number } {
    const time = Date.now() * 0.001;
    return {
      voice: 0.5 + Math.sin(time * 0.5) * 0.3, // Slow breathing-like pattern
      bass: 0.3 + Math.sin(time * 0.3) * 0.2,
      treble: 0.2 + Math.sin(time * 0.7) * 0.1
    };
  }
}