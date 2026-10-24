/* Official FalkorDB Canvas adapter. All graph data stays on this page. */
import "/static/vendor/falkordb/index.js";

const canvas = document.getElementById("falkordb-people-canvas");
const basic = document.getElementById("conference-graph");
const label = document.getElementById("graph-renderer-label");
const palette = {mirror: "#3eae91", missing_piece: "#e4a23d", unexpected_connection: "#9f7add"};
const edgePalette = {interest: "#ad94ce", co_speaker: "#4f92cd", shared_work: "#e2a24a", coauthor: "#ac7bca"};
let signature = "", queued = null, running = false, initialized = false;
let lastDimension = "", lastLayout = "", lastWidth = 0, lastHeight = 0;

let fitTimer;
function fit() {
  if (canvas.hidden) return;
  // Keep the whole neighborhood in view; a short path must not fill the camera.
  canvas.zoomToFit(canvas.getDimension() === "3d" ? 2.1 : 0.9);
  const maximumAutoZoom = canvas.getDimension() === "3d" ? 0.45 : 1.3;
  const zoom = canvas.getZoom();
  if (Number.isFinite(zoom) && zoom > maximumAutoZoom) canvas.zoom(maximumAutoZoom);
}
function scheduleFit() {
  window.clearTimeout(fitTimer);
  fitTimer = window.setTimeout(fit, 120);
}

function fallback() {
  canvas.hidden = true;
  basic.style.display = "block";
  label.textContent = "Basic orbit view";
}

async function apply(options) {
  const {graph, edges, dimension, layout, onSelect} = options;
  const targetId = graph.target_id || graph.center_id;
  const userSource = graph.comparison_source && graph.comparison_source === document.getElementById("graph-my-profile").value;
  const route = graph.shortest_path;
  const routeIds = new Set(route?.status === "ok" ? route.persons : []);
  const routeKeys = new Set((route?.edges || []).map(e => JSON.stringify([...[e.source, e.target].sort(), e.category])));
  const isPathEdge = e => routeKeys.has(JSON.stringify([...[e.source, e.target].sort(), e.category]));
  const nextSignature = JSON.stringify([graph.center_id, targetId, route?.persons, graph.comparison_source, graph.nodes.map(n => [n.id, n.connection_type]),
    edges.map(e => [e.source, e.target, e.category])]);
  const lookup = new Map(graph.nodes.map((n, i) => [n.id, i + 1]));
  canvas.hidden = false;
  const width = Math.max(240, canvas.parentElement.clientWidth);
  const height = window.innerWidth <= 800 ? 410 : Math.min(620, width * 0.87);
  if (!initialized) {
    canvas.setConfig({
      width, height, backgroundColor: "#edf2e9", foregroundColor: "#233d31",
      captionsKeys: ["name"], showPropertyKeyPrefix: false,
      nodeStyle: {fontFamily: "system-ui, sans-serif", textFillRatio: 0.8},
      linkStyle: {fontFamily: "system-ui, sans-serif"},
      simulation: {chargeStrength: -180, centerStrength: 0.06, warmupTicks: 100},
      interaction: {zoomToFitPadding: 0.16},
      isNodeSelected: node => node.data?.personId === queued?.graph.center_id,
      eventHandlers: {onEngineStop: scheduleFit, onNodeClick: node => {
        const selected = node.data?.personId;
        if (node.data?.kind === "topic" || node.data?.kind === "self") {
          window.dispatchEvent(new CustomEvent("graph-context-node", {detail: node.data}));
        } else if (typeof selected === "string") onSelect(selected);
      }},
    });
    initialized = true;
  }
  if (width !== lastWidth || height !== lastHeight) {
    canvas.style.height = `${height}px`;
    canvas.setWidth(width);
    canvas.setHeight(height);
    lastWidth = width;
    lastHeight = height;
  }
  const dataChanged = nextSignature !== signature;
  if (dataChanged) {
    canvas.setConfig({
      isNodeSelected: node => node.data?.personId === targetId || node.data?.personId === graph.comparison_source,
      isLinkSelected: link => link.data?.onPath === true,
      dimmed: false, dimOpacity: 1,
      isNodeDimmed: node => !routeIds.has(node.data?.personId),
      isLinkDimmed: link => link.data?.onPath !== true,
    });
    canvas.setData({
      nodes: graph.nodes.map((n, i) => ({id: i + 1, labels: [n.kind === "topic" ? "Topic" : "Person"], visible: true,
        shape: n.kind === "topic" ? "square" : "circle",
        ...(n.kind === "self" ? {x: 0, y: 0, z: 0, fx: 0, fy: 0, fz: 0} : {}),
        size: n.kind === "topic" ? 12 : n.kind === "self" || n.id === targetId ? 28 : 20,
        color: n.kind === "topic" ? "#af95d0" : n.id === graph.comparison_source ? "#3c83c4" : n.id === targetId ? "#254e3b" : routeIds.has(n.id) ? "#e3a23f" : palette[n.connection_type]
          || (n.roles.includes("confirmed_attendee") ? "#61afc3" : "#e8c174"),
        caption: "name", data: {name: (userSource && n.id === graph.comparison_source ? `You · ${n.name}` : n.name).replace(/[<>&]/g, char => ({"<": "‹", ">": "›", "&": "＆"}[char])), personId: n.id, kind: n.kind || "person", topics: n.topics || []}})),
      links: edges.filter(e => lookup.has(e.source) && lookup.has(e.target)).map((e, i) => ({
        id: i + 1, source: lookup.get(e.source), target: lookup.get(e.target),
        relationship: {interest: "Topic link", co_speaker: "Co-presented", shared_work: "Shared work", coauthor: "Coauthored"}[e.category],
        color: isPathEdge(e) ? "#ed9a27" : edgePalette[e.category] || "#8caa95", visible: true, width: isPathEdge(e) ? 4 : 1.5, arrowSize: 0,
        data: {onPath: isPathEdge(e)},
      })),
    });
    signature = nextSignature;
  }
  if (lastLayout !== layout) { canvas.setLayout(layout); lastLayout = layout; }
  const dimensionChanged = lastDimension !== dimension;
  if (dimensionChanged) {
    try { await canvas.setDimension(dimension); lastDimension = dimension; }
    catch (_) {
      lastDimension = "2d";
      document.getElementById("graph-3d-toggle").checked = false;
      label.textContent = "FalkorDB Canvas · 2D (3D unavailable)";
    }
  }
  basic.style.display = "none";
  if (dimensionChanged || dataChanged) scheduleFit();
  if (lastDimension === dimension) label.textContent = `FalkorDB Canvas · ${lastDimension.toUpperCase()}`;
  document.getElementById("graph-rotate-hint").textContent = lastDimension === "3d"
    ? "Drag empty space to rotate · Scroll to zoom · Right-drag to pan"
    : "Drag to pan · Scroll to zoom · Enable 3D to rotate";
}

window.WarmOpenGraphKit = {
  update(options) {
    queued = options;
    if (running) return;
    running = true;
    (async () => {
      let current;
      do { current = queued; await apply(current); } while (current !== queued);
    })().catch(fallback).finally(() => { running = false; });
  },
  fit,
  zoom(factor) { if (!canvas.hidden) canvas.zoom(canvas.getZoom() * factor); },
};
new ResizeObserver(() => {
  if (queued) window.WarmOpenGraphKit.update(queued);
}).observe(canvas.parentElement);
window.dispatchEvent(new Event("falkordb-canvas-ready"));
