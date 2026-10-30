// Adapted from Sphere-Light-Render-ComfyUI cc89da68f898ddabb6fddbfb0781d3999550ac18.
// Copyright 2026 Eric Venti and Christopher Connock; MIT. See LICENSE.
import * as THREE from "./three.module.js";
// Pure light-position math, kept free of any ComfyUI (`app`) import so it stays
// unit-testable under `node --test`.
export function lightPosition(azDeg, elDeg, r = 10) {
  const az = (azDeg * Math.PI) / 180;
  const el = (elDeg * Math.PI) / 180;
  return {
    x: r * Math.cos(el) * Math.sin(az),
    y: r * Math.sin(el),
    z: r * Math.cos(el) * Math.cos(az),
  };
}

export function buildScene() {
  const R = THREE;
  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 512;

  const renderer = new R.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = R.PCFSoftShadowMap;
  renderer.setSize(512, 512, false);
  renderer.setClearColor(0x8a8a8a);
  renderer.outputEncoding = R.sRGBEncoding;

  const scene = new R.Scene();
  scene.background = new R.Color(0x8a8a8a);

  const camera = new R.PerspectiveCamera(35, 1, 0.1, 200);
  camera.position.set(0, 6, 8);
  camera.lookAt(0, -0.5, 0);

  const plane = new R.Mesh(
    new R.PlaneGeometry(100, 100),
    new R.MeshStandardMaterial({ color: 0x8a8a8a, roughness: 1, metalness: 0 })
  );
  plane.rotation.x = -Math.PI / 2;
  plane.position.y = -1;
  plane.receiveShadow = true;
  scene.add(plane);

  const sphere = new R.Mesh(
    new R.SphereGeometry(1, 64, 64),
    new R.MeshStandardMaterial({ color: 0xcccccc, roughness: 0.8, metalness: 0 })
  );
  sphere.position.y = 0;
  sphere.castShadow = true;
  sphere.receiveShadow = true;
  scene.add(sphere);

  scene.add(new R.AmbientLight(0xffffff, 0.2));

  const dirLight = new R.DirectionalLight(0xffffff, 1.5);
  dirLight.castShadow = true;
  dirLight.shadow.mapSize.width  = 2048;
  dirLight.shadow.mapSize.height = 2048;
  dirLight.shadow.camera.near   = 0.1;
  dirLight.shadow.camera.far    = 50;
  dirLight.shadow.camera.left   = -8;
  dirLight.shadow.camera.right  =  8;
  dirLight.shadow.camera.top    =  8;
  dirLight.shadow.camera.bottom = -8;
  dirLight.shadow.bias = -0.0005;
  dirLight.shadow.radius = 2;
  scene.add(dirLight);

  return { renderer, scene, camera, dirLight, canvas };
}

// One WebGL renderer/scene shared by ALL sphere-light nodes. Browsers cap
// live WebGL contexts (~8–16), so per-node renderers stopped rendering once a
// workflow held enough nodes. Each node renders its own angles into the
// shared canvas, then copies the pixels to its own 2D snapshot canvas — so
// every node still displays its own image simultaneously, but only one GL
// context ever exists (and it lives for the page, so there's nothing to free
// per node).
let _shared = null;
export function sharedScene() {
  return (_shared ??= buildScene());
}

export function renderLight(ctx, { az, el, intensity }) {
  const p = lightPosition(az, el);
  ctx.dirLight.position.set(p.x, p.y, p.z);
  ctx.dirLight.intensity = intensity;
  ctx.renderer.shadowMap.needsUpdate = true;
  ctx.renderer.render(ctx.scene, ctx.camera);
  return ctx.canvas.toDataURL("image/png");
}


export function renderSphere(rotation, elevation, intensity) {
  return renderLight(sharedScene(), { az: rotation, el: elevation, intensity });
}
