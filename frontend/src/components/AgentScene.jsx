import { useEffect, useRef } from "react";
import * as THREE from "three";
import { roleMeta } from "../data/agents";

function buildHelmet(color) {
  const group = new THREE.Group();
  const shell = new THREE.Mesh(
    new THREE.SphereGeometry(0.56, 28, 28),
    new THREE.MeshStandardMaterial({ color: 0x0a1020, metalness: 0.92, roughness: 0.18 }),
  );
  group.add(shell);

  const visor = new THREE.Mesh(
    new THREE.SphereGeometry(0.58, 24, 12, -Math.PI * 0.3, Math.PI * 0.6, Math.PI * 0.32, Math.PI * 0.34),
    new THREE.MeshStandardMaterial({
      color,
      emissive: new THREE.Color(color),
      emissiveIntensity: 0.75,
      transparent: true,
      opacity: 0.78,
      metalness: 0.15,
      roughness: 0.05,
      side: THREE.DoubleSide,
    }),
  );
  visor.position.z = 0.08;
  group.add(visor);

  const ridge = new THREE.Mesh(
    new THREE.TorusGeometry(0.62, 0.018, 8, 48, Math.PI),
    new THREE.MeshStandardMaterial({ color, emissive: new THREE.Color(color), emissiveIntensity: 0.32, metalness: 1 }),
  );
  ridge.position.y = 0.12;
  group.add(ridge);

  const collar = new THREE.Mesh(
    new THREE.CylinderGeometry(0.34, 0.48, 0.24, 20),
    new THREE.MeshStandardMaterial({ color: 0x0a1424, metalness: 0.9, roughness: 0.22 }),
  );
  collar.position.y = -0.72;
  group.add(collar);

  const light = new THREE.PointLight(color, 1.4, 2.6);
  light.position.set(0, 0, 0.8);
  group.add(light);
  return group;
}

export function AgentScene({ agents, selectedRole, onSelectRole }) {
  const mountRef = useRef(null);
  const onSelectRef = useRef(onSelectRole);
  onSelectRef.current = onSelectRole;

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return undefined;

    const width = mount.clientWidth || window.innerWidth;
    const height = mount.clientHeight || window.innerHeight;
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    mount.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x020408, 0.018);
    const camera = new THREE.PerspectiveCamera(55, width / height, 0.1, 200);
    camera.position.set(0, 7.8, 17);
    camera.lookAt(0, 0, 0);

    scene.add(new THREE.AmbientLight(0x0a0f1f, 3));
    const key = new THREE.DirectionalLight(0x00e5ff, 1.2);
    key.position.set(5, 15, 8);
    scene.add(key);
    const rim = new THREE.DirectionalLight(0x7c4dff, 0.85);
    rim.position.set(-8, 5, -10);
    scene.add(rim);

    const grid = new THREE.GridHelper(46, 38, 0x00e5ff, 0x001520);
    grid.position.y = -3.15;
    grid.material.opacity = 0.18;
    grid.material.transparent = true;
    scene.add(grid);

    const centralOrb = new THREE.Mesh(new THREE.SphereGeometry(0.45, 28, 28), new THREE.MeshBasicMaterial({ color: 0x00e5ff }));
    centralOrb.position.y = 0.8;
    scene.add(centralOrb);
    const centralLight = new THREE.PointLight(0x00e5ff, 2.2, 9);
    centralLight.position.copy(centralOrb.position);
    scene.add(centralLight);

    [7, 10, 13].forEach((radius, index) => {
      const ring = new THREE.Mesh(
        new THREE.TorusGeometry(radius, 0.008, 8, 96),
        new THREE.MeshBasicMaterial({ color: index === 1 ? 0x7c4dff : 0x00e5ff, transparent: true, opacity: 0.2 - index * 0.04 }),
      );
      ring.rotation.x = Math.PI / 2;
      ring.position.y = -3.08;
      ring.userData.spin = index % 2 ? -0.05 : 0.08;
      scene.add(ring);
    });

    const pods = [];
    agents.forEach((agent, index) => {
      const meta = roleMeta(agent.role);
      const angle = (index / agents.length) * Math.PI * 2 - Math.PI / 2;
      const radius = 6.4;
      const group = new THREE.Group();
      group.position.set(Math.cos(angle) * radius, 0, Math.sin(angle) * radius);
      group.userData.role = agent.role;

      const platform = new THREE.Mesh(
        new THREE.CylinderGeometry(0.88, 1.0, 0.18, 6),
        new THREE.MeshStandardMaterial({ color: 0x0b1428, metalness: 0.9, roughness: 0.25, emissive: new THREE.Color(meta.three), emissiveIntensity: 0.06 }),
      );
      platform.position.y = -2.9;
      group.add(platform);

      const podRing = new THREE.Mesh(
        new THREE.TorusGeometry(0.92, 0.04, 8, 48),
        new THREE.MeshBasicMaterial({ color: meta.three, transparent: true, opacity: 0.48 }),
      );
      podRing.rotation.x = Math.PI / 2;
      podRing.position.y = -2.78;
      group.add(podRing);
      group.userData.podRing = podRing;

      const helmet = buildHelmet(meta.three);
      helmet.position.y = 0.35;
      helmet.rotation.y = -angle + Math.PI;
      group.add(helmet);
      group.userData.helmet = helmet;

      const dataRing = new THREE.Mesh(
        new THREE.TorusGeometry(0.9, 0.008, 6, 60),
        new THREE.MeshBasicMaterial({ color: meta.three, transparent: true, opacity: 0.32 }),
      );
      dataRing.rotation.x = Math.PI * 0.35;
      dataRing.position.y = 0.3;
      group.add(dataRing);
      group.userData.dataRing = dataRing;

      const line = new THREE.Line(
        new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, 0, 0), new THREE.Vector3(-Math.cos(angle) * radius, 0, -Math.sin(angle) * radius)]),
        new THREE.LineBasicMaterial({ color: meta.three, transparent: true, opacity: 0.14 }),
      );
      group.add(line);
      group.userData.line = line;
      scene.add(group);
      pods.push(group);
    });

    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();
    const handleClick = (event) => {
      const bounds = renderer.domElement.getBoundingClientRect();
      mouse.x = ((event.clientX - bounds.left) / bounds.width) * 2 - 1;
      mouse.y = -((event.clientY - bounds.top) / bounds.height) * 2 + 1;
      raycaster.setFromCamera(mouse, camera);
      const meshes = [];
      pods.forEach((pod) => pod.traverse((child) => child.isMesh && meshes.push(child)));
      const hits = raycaster.intersectObjects(meshes);
      if (!hits.length) return;
      let object = hits[0].object;
      while (object.parent && !object.userData.role) object = object.parent;
      if (object.userData.role) onSelectRef.current(object.userData.role);
    };
    renderer.domElement.addEventListener("click", handleClick);

    let frame = 0;
    const clock = new THREE.Clock();
    const animate = () => {
      frame = requestAnimationFrame(animate);
      const elapsed = clock.getElapsedTime();
      camera.position.x = Math.cos(elapsed * 0.08) * 15.5;
      camera.position.z = Math.sin(elapsed * 0.08) * 15.5;
      camera.lookAt(0, 0.4, 0);
      centralLight.intensity = 1.8 + Math.sin(elapsed * 2) * 0.35;
      scene.children.forEach((child) => {
        if (child.userData.spin) child.rotation.z += child.userData.spin * 0.015;
      });
      pods.forEach((pod, index) => {
        const isSelected = pod.userData.role === selectedRole;
        pod.position.y = Math.sin(elapsed * (isSelected ? 1.2 : 0.7) + index) * (isSelected ? 0.18 : 0.08);
        if (pod.userData.helmet) pod.userData.helmet.rotation.y += isSelected ? 0.012 : 0.004;
        if (pod.userData.dataRing) pod.userData.dataRing.rotation.z += isSelected ? 0.035 : 0.012;
        if (pod.userData.podRing?.material) pod.userData.podRing.material.opacity = isSelected ? 0.95 : 0.42;
        if (pod.userData.line?.material) pod.userData.line.material.opacity = isSelected ? 0.36 : 0.1;
      });
      renderer.render(scene, camera);
    };
    animate();

    const handleResize = () => {
      const nextWidth = mount.clientWidth || window.innerWidth;
      const nextHeight = mount.clientHeight || window.innerHeight;
      camera.aspect = nextWidth / nextHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(nextWidth, nextHeight);
    };
    window.addEventListener("resize", handleResize);

    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", handleResize);
      renderer.domElement.removeEventListener("click", handleClick);
      renderer.dispose();
      mount.innerHTML = "";
    };
  }, [agents, selectedRole]);

  return <div className="ox-3d-canvas" ref={mountRef} />;
}
