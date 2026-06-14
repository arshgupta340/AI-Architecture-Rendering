import { useEffect, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { PointerLockControls } from "@react-three/drei";
import * as THREE from "three";

/**
 * First-person walk/fly: click to lock the pointer (mouse looks), WASD moves along
 * the view direction, Space/Shift = up/down. Speed is in world units (feet)/sec.
 * Requires the Canvas frameloop to be "always" while active (App switches it by mode).
 */
export function WalkControls({ speed }: { speed: number }) {
  const camera = useThree((s) => s.camera);
  const invalidate = useThree((s) => s.invalidate);
  const keys = useRef<Record<string, boolean>>({});

  useEffect(() => {
    const dn = (e: KeyboardEvent) => (keys.current[e.code] = true);
    const up = (e: KeyboardEvent) => (keys.current[e.code] = false);
    window.addEventListener("keydown", dn);
    window.addEventListener("keyup", up);
    return () => {
      window.removeEventListener("keydown", dn);
      window.removeEventListener("keyup", up);
      keys.current = {};
    };
  }, []);

  const fwd = useRef(new THREE.Vector3());
  const right = useRef(new THREE.Vector3());
  const move = useRef(new THREE.Vector3());

  useFrame((_, dt) => {
    const k = keys.current;
    const m = move.current.set(0, 0, 0);
    camera.getWorldDirection(fwd.current);
    right.current.crossVectors(fwd.current, camera.up).normalize();
    if (k["KeyW"]) m.add(fwd.current);
    if (k["KeyS"]) m.sub(fwd.current);
    if (k["KeyD"]) m.add(right.current);
    if (k["KeyA"]) m.sub(right.current);
    if (k["Space"]) m.y += 1;
    if (k["ShiftLeft"] || k["ShiftRight"]) m.y -= 1;
    if (m.lengthSq() > 0) {
      m.normalize().multiplyScalar(speed * Math.min(dt, 0.05));
      camera.position.add(m);
      invalidate();
    }
  });

  return <PointerLockControls />;
}
