# Galaxy Visualization Integration Design Spec
2026-10-15-galaxy-visualization-design.md

## Overview

This document describes the integration of a living galaxy visualization into Mark-LV's UI, based on the specification provided in galaxy.md. The visualization will be implemented as a TypeScript/Vite/Three.js web application embedded within Mark-LV's existing PyQt6 interface using QtWebEngine.

## Core Requirements

### Visual Experience
- A wireframe icosahedron orb that serves as the central focus
- Deep-space nebula background with drifting layers
- Star network with colored clusters and connections
- State-based color and motion changes for the orb
- Audio-reactive visual elements (microphone and playback levels)
- Smooth transitions between states

### States to Visualize
1. **Idle**: dim teal, slow breathing, faint glow
2. **Arming**: dim ember (mic requested, no audio yet)
3. **Listening**: bright gold (recording light)
4. **Processing/Thinking**: teal shifting to purple with pulse and rings
5. **Speaking**: bright teal driven by playback audio
6. **Error**: red, still, sharp edge

### Audio Reactivity
- Voice level: average of frequency bins 10-60%
- Bass: first 6 frequency bins
- Treble: 65% and up
- Orb deformation based on audio levels
- Galaxy "swell" when speaking/thinking (network brightens, rotates faster, camera pushes in slightly)

## Technical Architecture

### Integration Approach
- Embedded web view using QtWebEngine within the existing PyQt6 UI
- Communication bridge between Python/JARVIS core and TypeScript visualization
- State updates via WebSocket or similar mechanism from Python to web view
- Audio level data passed from Python audio processing to visualization

### File Structure
```
Mark-LV/
├── galaxy/                     # New directory for web visualization
│   ├── src/                    # Source code
│   │   ├── components/         # Three.js components (orb, sky, network)
│   │   ├── shaders/            # Custom shader materials
│   │   ├── states/             # State definitions and transitions
│   │   ├── audio/              # Audio processing and level calculation
│   │   ├── utils/              # Math helpers, easing functions
│   │   ├── main.ts             # Entry point
│   │   └── index.html          # HTML template
│   ├── public/                 # Static assets
│   ├── vite.config.ts          # Vite configuration
│   ├── tsconfig.json           # TypeScript configuration
│   └── package.json            # Dependencies and scripts
├── ui.py                       # Modified to include QtWebEngine view
├── core/                       # Existing core functionality
│   └── galaxy_bridge.py        # New: Communication bridge
└── requirements.txt            # Updated with QtWebEngine if needed
```

### Communication Protocol
- Python/JARVIS sends state updates to web view via WebSocket or similar
- Web view renders visualization based on received state
- Audio level data sent from Python's audio processing system
- Initialization handshake to establish connection

## Implementation Plan

### Phase 1: Foundation
1. Set up TypeScript/Vite/Three.js project structure
2. Create basic Three.js scene with camera, renderer, and orbit controls
3. Implement wireframe icosahedron orb with basic material
4. Establish communication bridge between Python and web view

### Phase 2: Core Visualization
1. Implement nebula background shader with drifting noise layers
2. Create star network with clusters and connections
3. Add orbital rings that appear during thinking state
4. Implement basic state transitions (idle ↔ listening ↔ speaking)

### Phase 3: Audio Reactivity
1. Integrate audio level data from Python audio system
2. Implement vertex displacement based on simplex noise and audio
3. Add fresnel edge and glow shell effects
4. Implement galaxy-wide "swell" during speech/thinking

### Phase 4: States and Transitions
1. Implement all six states with distinct visual properties
2. Add smooth interpolation between states (no snapping)
3. Implement thinking state pulse and ring visibility
4. Add error state sharp edges and lack of motion

### Phase 5: Polish and Features
1. Implement dark/light theme switching
2. Add performance mode (adjust detail based on FPS)
3. Add reduced motion support
4. Create text live region for screen readers
5. Ensure proper cleanup and teardown

## Dependencies

### New Dependencies
- Three.js (core 3D library)
- simplex-noise (for vertex displacement)
- Vite (build tool)
- TypeScript
- QtWebEngine (if not already in requirements)

### Existing Dependencies to Leverage
- PyQt6 (UI framework)
- Existing audio processing system
- State management from JARVIS core

## Open Questions and Decisions

1. **Communication Mechanism**: WebSocket vs. Qt property system vs. custom bridge
2. **Audio Data Granularity**: Raw frequency bands vs. pre-processed levels
3. **Performance Targets**: Target FPS and detail levels for different hardware
4. **Asset Management**: How to handle shader files and textures
5. **Error Handling**: Graceful degradation if WebGL unavailable

## Success Criteria

- [ ] Wireframe orb renders correctly with basic material
- [ ] Nebula background with drifting layers visible
- [ ] Star network with clusters and connections rendered
- [ ] Orb changes color based on AI state (idle, listening, thinking, speaking, error)
- [ ] Orb deforms based on microphone input levels
- [ ] Galaxy brightens and swells during speech/thinking states
- [ ] Smooth transitions between states without snapping
- [ ] Dark/light theme switching functional
- [ ] Performance mode activates when FPS drops below threshold
- [ ] Reduced motion setting respected
- [ ] Text live region updates for screen reader accessibility
- [ ] Proper cleanup when widget is destroyed

## Related Files

This design affects or requires modifications to:
- `ui.py`: Add QtWebEngine container widget
- `core/`: New galaxy_bridge.py for communication
- `requirements.txt`: Add any new Python dependencies
- `galaxy/`: New directory with TypeScript/Vite/Three.js implementation
- `main.py`: Potentially initialize communication bridge

## Implementation Notes

Following the ponytail principle of lazy/efficient implementation:
- Start with minimal viable orb visualization
- Use existing Three.js examples as starting points where appropriate
- Leverage existing audio level calculations from JARVIS where possible
- Implement one layer at a time, verifying each works before proceeding
- Use frame-rate independent easing for smooth motion
- Keep math pure and testable where possible (separate from WebGL)

## Risks and Mitigations

1. **Performance Impact**: Mitigate by starting simple and adding complexity gradually
2. **Communication Latency**: Mitigate by batching updates and using efficient serialization
3. **WebGL Availability**: Mitigate by detecting WebGL support and falling back gracefully
4. **Audio Sync**: Mitigate by using timestamps or frame-based updates
5. **Bundle Size**: Mitigate by tree-shaking and lazy loading non-essential components