import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

const VIEW_NAMES = ["front", "back", "left", "right", "top", "bottom"];
const files = new Map();
const previewUrls = new Map();

const elements = {
  readyCount: document.getElementById("ready-count"),
  readyFill: document.getElementById("ready-fill"),
  reconstructButton: document.getElementById("reconstruct-button"),
  demoButton: document.getElementById("demo-button"),
  clearAll: document.getElementById("clear-all"),
  resolution: document.getElementById("resolution"),
  status: document.getElementById("status-line"),
  viewerCanvas: document.getElementById("viewer-canvas"),
  viewerStage: document.getElementById("viewer-stage"),
  viewerEmpty: document.getElementById("viewer-empty"),
  resetView: document.getElementById("reset-view"),
  metricVertices: document.getElementById("metric-vertices"),
  metricFaces: document.getElementById("metric-faces"),
  metricVoxels: document.getElementById("metric-voxels"),
  metricState: document.getElementById("metric-state"),
  downloads: {
    glb: document.getElementById("download-glb"),
    obj: document.getElementById("download-obj"),
    stl: document.getElementById("download-stl"),
  },
};

function setStatus(message, kind = "") {
  elements.status.className = `status-line ${kind}`.trim();
  elements.status.textContent = message;
}

function updateReadyState() {
  const count = files.size;
  elements.readyCount.textContent = `${count} / 6 views ready`;
  elements.readyFill.style.width = `${(count / VIEW_NAMES.length) * 100}%`;
  elements.reconstructButton.disabled = count !== VIEW_NAMES.length || isProcessing;
}

function setFile(viewName, file) {
  if (!(file instanceof File) || !file.type.startsWith("image/")) {
    setStatus(`The ${viewName} file is not a supported image. Choose PNG, JPG or WEBP.`, "error");
    return;
  }
  if (file.size > 12 * 1024 * 1024) {
    setStatus(`${viewName.toUpperCase()} is larger than 12 MB. Please choose a smaller image.`, "error");
    return;
  }

  files.set(viewName, file);
  const oldUrl = previewUrls.get(viewName);
  if (oldUrl) URL.revokeObjectURL(oldUrl);
  const objectUrl = URL.createObjectURL(file);
  previewUrls.set(viewName, objectUrl);

  const card = document.querySelector(`[data-view="${viewName}"]`);
  const image = card.querySelector("img");
  const hint = card.querySelector(".preview-hint");
  const fileStatus = card.querySelector(".file-status");
  image.src = objectUrl;
  image.hidden = false;
  hint.hidden = true;
  card.classList.add("has-file");
  fileStatus.textContent = file.name;
  updateReadyState();
  setStatus(`${viewName.toUpperCase()} view added.`, "success");
}

function clearFile(viewName) {
  files.delete(viewName);
  const oldUrl = previewUrls.get(viewName);
  if (oldUrl) URL.revokeObjectURL(oldUrl);
  previewUrls.delete(viewName);

  const card = document.querySelector(`[data-view="${viewName}"]`);
  const input = card.querySelector("input");
  const image = card.querySelector("img");
  const hint = card.querySelector(".preview-hint");
  input.value = "";
  image.removeAttribute("src");
  image.hidden = true;
  hint.hidden = false;
  card.classList.remove("has-file");
  card.querySelector(".file-status").textContent = "Waiting for image";
  updateReadyState();
}

for (const viewName of VIEW_NAMES) {
  const card = document.querySelector(`[data-view="${viewName}"]`);
  const input = card.querySelector("input");
  const clearButton = card.querySelector(".clear-file");

  card.addEventListener("click", (event) => {
    if (event.target.closest(".clear-file")) return;
    if (event.target !== input) input.click();
  });
  card.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      input.click();
    }
  });
  input.addEventListener("change", () => {
    const selected = input.files?.[0];
    if (selected) setFile(viewName, selected);
  });
  clearButton.addEventListener("click", (event) => {
    event.stopPropagation();
    clearFile(viewName);
  });

  card.addEventListener("dragover", (event) => {
    event.preventDefault();
    card.classList.add("drag-over");
  });
  card.addEventListener("dragleave", () => card.classList.remove("drag-over"));
  card.addEventListener("drop", (event) => {
    event.preventDefault();
    card.classList.remove("drag-over");
    const dropped = event.dataTransfer?.files?.[0];
    if (dropped) setFile(viewName, dropped);
  });
}

let isProcessing = false;

function makePngFile(viewName, width, height) {
  return new Promise((resolve, reject) => {
    const canvas = document.createElement("canvas");
    canvas.width = 512;
    canvas.height = 512;
    const context = canvas.getContext("2d");
    if (!context) {
      reject(new Error("Could not create the demo image canvas."));
      return;
    }

    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.fillStyle = "#17191f";
    context.beginPath();
    context.ellipse(256, 256, width / 2, height / 2, 0, 0, Math.PI * 2);
    context.fill();

    canvas.toBlob((blob) => {
      if (!blob) {
        reject(new Error("Could not generate a demo image."));
        return;
      }
      resolve(new File([blob], `${viewName}-demo.png`, { type: "image/png" }));
    }, "image/png");
  });
}

// The six ellipses are orthographic projections of one demonstration ellipsoid.
elements.demoButton.addEventListener("click", async () => {
  try {
    const dimensions = {
      front: [320, 270],
      back: [320, 270],
      left: [230, 270],
      right: [230, 270],
      top: [320, 230],
      bottom: [320, 230],
    };
    const demoFiles = await Promise.all(
      VIEW_NAMES.map(async (name) => {
        const [width, height] = dimensions[name];
        return [name, await makePngFile(name, width, height)];
      })
    );
    for (const [name, file] of demoFiles) setFile(name, file);
    setStatus("Demo silhouettes loaded. Run reconstruction to create the ellipsoid mesh.", "success");
  } catch (error) {
    setStatus(error.message || "Could not create the demo images.", "error");
  }
});

elements.clearAll.addEventListener("click", () => {
  for (const viewName of VIEW_NAMES) clearFile(viewName);
  setStatus("All six image slots have been cleared.");
});

// Three.js scene: Z is the up axis to match the reconstruction coordinate system.
let scene;
let camera;
let renderer;
let controls;
let placeholder;
let currentModel = null;
let animationFrame = 0;
let resizeObserver = null;

function initializeViewer() {
  try {
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0b111c);

    camera = new THREE.PerspectiveCamera(42, 1, 0.01, 100);
    camera.up.set(0, 0, 1);
    camera.position.set(2.6, -3.1, 2.5);

    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.25;
    elements.viewerCanvas.appendChild(renderer.domElement);

    controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(0, 0, 0);
    controls.enableDamping = true;
    controls.dampingFactor = 0.065;
    controls.minDistance = 1.1;
    controls.maxDistance = 12;
    controls.update();

    const hemisphere = new THREE.HemisphereLight(0xdde8ff, 0x263346, 2.1);
    scene.add(hemisphere);

    const keyLight = new THREE.DirectionalLight(0xffffff, 3.2);
    keyLight.position.set(3, -4, 5);
    scene.add(keyLight);

    const fillLight = new THREE.DirectionalLight(0x7ea8ff, 1.5);
    fillLight.position.set(-4, 2, 2.5);
    scene.add(fillLight);

    const rimLight = new THREE.PointLight(0x83d9cf, 30, 8);
    rimLight.position.set(1, 3, 1.8);
    scene.add(rimLight);

    const grid = new THREE.GridHelper(5, 20, 0x35465f, 0x253246);
    grid.rotation.x = Math.PI / 2;
    grid.position.z = -0.58;
    grid.material.transparent = true;
    grid.material.opacity = 0.45;
    scene.add(grid);

    const axes = new THREE.AxesHelper(0.8);
    axes.material.transparent = true;
    axes.material.opacity = 0.65;
    scene.add(axes);

    placeholder = new THREE.Mesh(
      new THREE.IcosahedronGeometry(0.82, 1),
      new THREE.MeshBasicMaterial({ color: 0x647fae, wireframe: true, transparent: true, opacity: 0.43 })
    );
    scene.add(placeholder);

    resizeObserver = new ResizeObserver(resizeViewer);
    resizeObserver.observe(elements.viewerStage);
    resizeViewer();
    animate();
  } catch (error) {
    console.error("VIEWFORGE viewer initialization failed:", error);
    elements.viewerEmpty.querySelector("strong").textContent = "3D viewer unavailable";
    elements.viewerEmpty.querySelector("span").textContent = "Check browser WebGL support and the internet connection for Three.js.";
  }
}

function resizeViewer() {
  if (!renderer || !camera) return;
  const width = Math.max(1, elements.viewerStage.clientWidth);
  const height = Math.max(1, elements.viewerStage.clientHeight);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
  renderer.setSize(width, height, false);
}

function animate() {
  animationFrame = requestAnimationFrame(animate);
  if (placeholder && !currentModel) placeholder.rotation.z += 0.0018;
  if (controls) controls.update();
  if (renderer && scene && camera) renderer.render(scene, camera);
}

function disposeObject(object) {
  object.traverse((child) => {
    if (child.geometry) child.geometry.dispose();
    if (child.material) {
      const materials = Array.isArray(child.material) ? child.material : [child.material];
      materials.forEach((material) => material.dispose());
    }
  });
}

function showModel(glbUrl) {
  return new Promise((resolve, reject) => {
    const loader = new GLTFLoader();
    loader.load(
      `${glbUrl}?t=${Date.now()}`,
      (gltf) => {
        if (currentModel) {
          scene.remove(currentModel);
          disposeObject(currentModel);
          currentModel = null;
        }
        if (placeholder) placeholder.visible = false;

        const model = gltf.scene;
        const bounds = new THREE.Box3().setFromObject(model);
        const center = bounds.getCenter(new THREE.Vector3());
        const size = bounds.getSize(new THREE.Vector3());
        const maximumDimension = Math.max(size.x, size.y, size.z) || 1;

        model.position.sub(center);
        model.scale.setScalar(2.15 / maximumDimension);
        scene.add(model);
        currentModel = model;
        elements.viewerEmpty.hidden = true;

        controls.target.set(0, 0, 0);
        camera.position.set(2.7, -3.2, 2.6);
        controls.update();
        resolve();
      },
      undefined,
      (error) => reject(error)
    );
  });
}

function formatNumber(value) {
  return Number(value).toLocaleString("en-US");
}

function setDownloadLink(anchor, url, extension) {
  anchor.href = url;
  anchor.download = `viewforge-model.${extension}`;
  anchor.classList.remove("disabled");
  anchor.removeAttribute("aria-disabled");
}

function resetOutputs() {
  elements.metricVertices.textContent = "—";
  elements.metricFaces.textContent = "—";
  elements.metricVoxels.textContent = "—";
  elements.metricState.textContent = "—";
  elements.metricState.classList.remove("good");
  for (const anchor of Object.values(elements.downloads)) {
    anchor.href = "#";
    anchor.classList.add("disabled");
    anchor.setAttribute("aria-disabled", "true");
    anchor.removeAttribute("download");
  }
}

async function reconstruct() {
  if (files.size !== VIEW_NAMES.length || isProcessing) return;
  isProcessing = true;
  updateReadyState();
  elements.reconstructButton.innerHTML = '<span class="spinner"></span> Computing visual hull…';
  setStatus("Extracting silhouettes, carving voxels and generating the mesh. Larger resolutions take longer.");

  const formData = new FormData();
  for (const viewName of VIEW_NAMES) {
    formData.append(viewName, files.get(viewName), files.get(viewName).name);
  }
  formData.append("resolution", elements.resolution.value);

  try {
    const response = await fetch("/api/reconstruct", { method: "POST", body: formData });
    const result = await response.json();
    if (!response.ok) {
      throw new Error(result.detail || `Server returned ${response.status}.`);
    }

    const stats = result.statistics;
    elements.metricVertices.textContent = formatNumber(stats.vertices);
    elements.metricFaces.textContent = formatNumber(stats.faces);
    elements.metricVoxels.textContent = formatNumber(stats.occupied_voxels);
    elements.metricState.textContent = stats.watertight ? "Closed" : "Open";
    if (stats.watertight) elements.metricState.classList.add("good");

    setDownloadLink(elements.downloads.glb, result.downloads.glb, "glb");
    setDownloadLink(elements.downloads.obj, result.downloads.obj, "obj");
    setDownloadLink(elements.downloads.stl, result.downloads.stl, "stl");

    setStatus(`Mesh generated · ${stats.vertices.toLocaleString()} vertices · ${stats.faces.toLocaleString()} faces · dimensions ${stats.dimensions.join(" × ")}.`, "success");
    await showModel(result.downloads.glb);
  } catch (error) {
    console.error("VIEWFORGE reconstruction error:", error);
    setStatus(error.message || "Something went wrong while reconstructing the model.", "error");
  } finally {
    isProcessing = false;
    elements.reconstructButton.innerHTML = '<span class="button-icon">✧</span> Reconstruct 3D model <span>→</span>';
    updateReadyState();
  }
}

elements.reconstructButton.addEventListener("click", reconstruct);
elements.resetView.addEventListener("click", () => {
  if (!camera || !controls) return;
  camera.position.set(2.6, -3.1, 2.5);
  controls.target.set(0, 0, 0);
  controls.update();
});

window.addEventListener("beforeunload", () => {
  if (animationFrame) cancelAnimationFrame(animationFrame);
  if (resizeObserver) resizeObserver.disconnect();
  for (const url of previewUrls.values()) URL.revokeObjectURL(url);
  if (renderer) renderer.dispose();
});

initializeViewer();
updateReadyState();
