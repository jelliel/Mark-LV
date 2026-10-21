import * as THREE from 'three';

export function createStarNetwork(scene: THREE.Scene) {
  // Create a group for the star network
  const group = new THREE.Group();
  scene.add(group);

  // Store original positions for animation
  const nodes: {
    mesh: THREE.Mesh;
    originalPosition: THREE.Vector3;
    color: THREE.Color;
    size: number;
  }[] = [];

  const lines: THREE.Line[] = [];

  // Parameters from galaxy.md
  const clusterCount = 8;
  const nodesPerCluster = 7; // Average of 6-8
  const strayNodes = 100 - (clusterCount * nodesPerCluster); // About 100 total nodes
  const clusterRadiusRange = { min: 13, max: 25 };
  const connectionDistance = 10;
  const lineOpacity = 0.12; // 12% opacity

  // Color palette for clusters (cool colors)
  const clusterColors = [
    0x00ffff, // teal/cyan
    0x00ffff, // cyan
    0x0000ff, // blue
    0x800080, // purple
    0x008080, // green-teal
    0x4b0082, // indigo
    0x00ced1, // blue-teal
    0x9400d3  // violet
  ];

  // Stray node color (muted blue-grey)
  const strayColor = 0x666688;

  // Create cluster centers
  const clusterCenters: THREE.Vector3[] = [];
  for (let i = 0; i < clusterCount; i++) {
    // Distribute clusters on a shell
    const radius = THREE.MathUtils.lerp(
      clusterRadiusRange.min,
      clusterRadiusRange.max,
      i / clusterCount
    );
    const phi = Math.acos(2 * i / clusterCount - 1);
    const theta = Math.sqrt(clusterCount * Math.PI) * i;

    const center = new THREE.Vector3(
      radius * Math.sin(phi) * Math.cos(theta),
      radius * Math.sin(phi) * Math.sin(theta),
      radius * Math.cos(phi)
    );
    clusterCenters.push(center);
  }

  // Create nodes in clusters
  clusterCenters.forEach((center, clusterIndex) => {
    const color = new THREE.Color(clusterColors[clusterIndex % clusterColors.length]);

    for (let i = 0; i < nodesPerCluster; i++) {
      // Spread nodes within a few units of center
      const offset = new THREE.Vector3(
        (Math.random() - 0.5) * 4,
        (Math.random() - 0.5) * 4,
        (Math.random() - 0.5) * 4
      );
      const position = center.clone().add(offset);

      // Create node sprite (we'll use a simple sphere for now)
      const geometry = new THREE.SphereGeometry(0.1, 8, 8);
      const material = new THREE.MeshBasicMaterial({
        color: color,
        transparent: true,
        opacity: 0.8
      });

      const mesh = new THREE.Mesh(geometry, material);
      mesh.position.copy(position);
      group.add(mesh);

      nodes.push({
        mesh,
        originalPosition: position.clone(),
        color,
        size: 0.1
      });
    }
  });

  // Create stray nodes
  for (let i = 0; i < strayNodes; i++) {
    const position = new THREE.Vector3(
      (Math.random() - 0.5) * 50,
      (Math.random() - 0.5) * 50,
      (Math.random() - 0.5) * 50
    );

    const geometry = new THREE.SphereGeometry(0.08, 6, 6);
    const material = new THREE.MeshBasicMaterial({
      color: new THREE.Color(strayColor),
      transparent: true,
      opacity: 0.6
    });

    const mesh = new THREE.Mesh(geometry, material);
    mesh.position.copy(position);
    group.add(mesh);

    nodes.push({
      mesh,
      originalPosition: position.clone(),
      color: new THREE.Color(strayColor),
      size: 0.08
    });
  }

  // Create connections between nearby nodes
  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      const dist = nodes[i].originalPosition.distanceTo(nodes[j].originalPosition);
      if (dist < connectionDistance) {
        // Create line between nodes
        const material = new THREE.LineBasicMaterial({
          color: new THREE.Color(
            (nodes[i].color.getHex() + nodes[j].color.getHex()) / 2
          ),
          transparent: true,
          opacity: lineOpacity
        });

        const geometry = new THREE.BufferGeometry().setFromPoints([
          nodes[i].originalPosition,
          nodes[j].originalPosition
        ]);

        const line = new THREE.Line(geometry, material);
        group.add(line);
        lines.push(line);
      }
    }
  }

  // Animation parameters
  let time = 0;
  const networkRotationSpeed = 0.0005; // Very slow turn
  const networkTiltRange = 0.2; // Gentle back and forth tilt
  const cameraDriftSpeed = 0.0001; // Couple of units over minutes

  return {
    update: (delta: number, state: string, levels: { voice: number, bass: number, treble: number }) => {
      time += delta;

      // Update group rotation and tilt (star network motion)
      group.rotation.y += time * networkRotationSpeed;
      group.rotation.x = Math.sin(time * 0.3) * networkTiltRange;
      group.position.z = Math.sin(time * 0.2) * cameraDriftSpeed * 10;

      // State-based effects
      const isThinking = state === 'thinking';
      const isSpeaking = state === 'speaking';

      // Update node properties based on state
      nodes.forEach(node => {
        // Base pulse
        let pulse = 1.0;

        if (isThinking) {
          // Thinking state: nodes grow and brighten
          pulse = 1.0 + Math.sin(time * 3) * 0.3;
          // Increase opacity
          node.mesh.material.opacity = 0.6 + Math.sin(time * 2) * 0.2;
        } else if (isSpeaking || isListening) {
          // Speaking/Listening: moderate pulse
          pulse = 1.0 + Math.sin(time * 2) * 0.1;
        }

        // Apply scale
        const scale = node.size * pulse;
        node.mesh.scale.set(scale, scale, scale);

        // Update line opacity for thinking state (lines brighten)
        if (isThinking) {
          // Find connected lines and increase their opacity
          // This is simplified - in reality we'd need to track which lines connect to which nodes
        }
      });

      // Update line opacities for thinking state
      if (isThinking) {
        lines.forEach(line => {
          const baseOpacity = lineOpacity;
          const pulseOpacity = baseOpacity + Math.sin(time * 2) * 0.03; // Pulse toward 65% opacity
          line.material.opacity = Math.min(0.65, pulseOpacity);
        });
      } else {
        lines.forEach(line => {
          line.material.opacity = lineOpacity;
        });
      }

      // Network swelling during speech/thinking (few percent)
      const swellFactor = (isSpeaking || isThinking) ? 1.03 : 1.0;
      group.scale.set(swellFactor, swellFactor, swellFactor);

      // Camera push-in during speech/thinking
      // This would be handled in the main render loop by adjusting camera position
    }
  };
}