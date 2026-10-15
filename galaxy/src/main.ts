import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { GUI } from 'three/examples/jsm/libs/lil-gui.module.min.js';
import { createOrb } from './components/orb.js';
import { createSky } from './components/sky.js';
import { createStarNetwork } from './components/starNetwork.js';
import { StateManager } from './states/stateManager.js';
import { AudioAnalyzer } from './audio/audioAnalyzer.js';

// Scene setup
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x00060a); // Deep space navy

const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 1000);
camera.position.set(0, 0, 4.2); // Position as specified in galaxy.md

const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2)); // Cap at 2 as specified
document.getElementById('app').appendChild(renderer.domElement);

// Controls (for development - remove in production)
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;

// State management
const stateManager = new StateManager();

// Audio analysis
const audioAnalyzer = new AudioAnalyzer();

// Galaxy components
const orb = createOrb(scene);
const sky = createSky(scene);
const starNetwork = createStarNetwork(scene);

// Debug GUI (remove in production)
const gui = new GUI();
gui.add(stateManager, 'state', ['idle', 'arming', 'listening', 'thinking', 'speaking', 'error']);

// Animation loop
const clock = new THREE.Clock();

function animate() {
  requestAnimationFrame(animate);

  const delta = clock.getDelta();

  // Update controls
  controls.update();

  // Get audio levels
  const audioLevels = audioAnalyzer.getLevels();

  // Update state based on audio (for demo - in real implementation this comes from JARVIS)
  if (audioLevels.voice > 0.1) {
    stateManager.setState('speaking');
  } else if (audioLevels.voice > 0.05) {
    stateManager.setState('listening');
  } else {
    stateManager.setState('idle');
  }

  // Update components
  orb.update(delta, stateManager.getCurrentState(), audioLevels);
  sky.update(delta, stateManager.getCurrentState(), audioLevels);
  starNetwork.update(delta, stateManager.getCurrentState(), audioLevels);

  renderer.render(scene, camera);
}

animate();

// Handle window resize
window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

// Expose for communication with JARVIS core
window.galaxyAPI = {
  setState: (state) => stateManager.setState(state),
  setAudioLevels: (levels) => audioAnalyzer.setLevels(levels),
  getState: () => stateManager.getCurrentState()
};