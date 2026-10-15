export class StateManager {
  private state: string = 'idle';

  constructor() {
    // Default to idle state
  }

  setState(state: string): void {
    this.state = state;
  }

  getCurrentState(): string {
    return this.state;
  }
}