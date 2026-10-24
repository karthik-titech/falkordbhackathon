"use strict";
const $ = id => document.getElementById(id);
document.title = `${PRODUCT_NAME} · Public graph exploration`;
$("try-product-name").textContent = PRODUCT_NAME;
let people = [], names = {}, evidence = {}, example = null, busy = false;

function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  if (className) element.className = className;
  return element;
}
function sourceLink(url, label) {
  const link = node("a", label);
  try {
    const parsed = new URL(url);
    if (["https:", "http:"].includes(parsed.protocol)) {
      link.href = parsed.href; link.target = "_blank"; link.rel = "noopener noreferrer";
    }
  } catch (_) { /* Keep malformed sources as plain text. */ }
  return link;
}
async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : {
    method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Request failed");
  Object.assign(names, data.people || {});
  Object.assign(evidence, data.evidence || {});
  return data;
}
function controls() {
  for (const id of ["try-source", "try-target", "try-source-filter", "try-target-filter"])
    $(id).disabled = busy || !people.length;
  for (const id of ["try-paths", "try-openers"]) {
    $(id).disabled = busy || !$("try-source").value || !$("try-target").value
      || $("try-source").value === $("try-target").value;
  }
  $("try-example").disabled = busy || !example;
}
function populateSelect(selectId, filterId) {
  const select = $(selectId), previous = select.value, term = $(filterId).value.trim().toLowerCase();
  const matches = people.filter(person => person.name.toLowerCase().includes(term));
  const placeholder = new Option("Choose a public profile", ""); placeholder.disabled = true;
  select.replaceChildren(placeholder, ...matches.map(person => new Option(person.name, person.id)));
  if (matches.some(person => person.id === previous)) select.value = previous;
  else select.value = "";
}
async function action(kind) {
  if (busy) return;
  busy = true; controls();
  $("try-status").textContent = "Searching cited public graph facts…";
  try {
    const data = await api("/api/try", {source: $("try-source").value,
      target: $("try-target").value, action: kind});
    render(data, kind);
  } catch (error) { $("try-status").textContent = error.message; }
  finally { busy = false; controls(); }
}
function renderPathResults(routes, truncated) {
  const container = $("try-path-results"); container.replaceChildren();
  container.append(node("h2", "Public graph paths"));
  if (!routes.length) {
    container.append(node("p", truncated
      ? "Search limit reached before a cited public path was found. Other paths may exist."
      : "No cited public path was found within six hops."));
    return;
  }
  for (const route of routes) {
    const card = node("article", undefined, "try-route"), namesInRoute = route.persons.map(id => names[id] || id);
    card.append(node("h3", `${route.hops} ${route.hops === 1 ? "link" : "links"} · ${namesInRoute.join(" → ")}`));
    for (const edge of route.edges) {
      const from = names[edge.from] || edge.from, to = names[edge.to] || edge.to;
      const row = node("p", `${from} → ${to} · ${edge.category}. `, "claim");
      const primary = evidence[edge.evidence_id];
      const secondary = evidence[edge.other_evidence_id];
      if (primary) row.append(sourceLink(primary.url, primary.claim || "Public source"));
      else row.append(node("span", "No public citation."));
      if (secondary && edge.other_evidence_id !== edge.evidence_id) {
        row.append(document.createTextNode(" · "), sourceLink(secondary.url, secondary.claim || "Other public source"));
      }
      card.append(row);
    }
    container.append(card);
  }
  if (truncated) container.append(node("p", "Search limit reached; showing the routes found so far.", "claim"));
}
function renderOpeners(items) {
  const container = $("try-opener-results"); container.replaceChildren();
  container.append(node("h2", "Sourced opener templates"));
  for (const item of items) {
    const card = node("article", undefined, "try-cue"), cited = evidence[item.evidence_id];
    card.append(node("p", `“${item.text}”`));
    if (cited) card.append(sourceLink(cited.url, "Source"), node("p", cited.claim, "claim"));
    else card.append(node("p", "General template · no source available", "claim"));
    container.append(card);
  }
}
function render(data, kind) {
  renderPathResults(data.routes, data.truncated);
  if (kind === "openers") renderOpeners(data.openers || []);
  else $("try-opener-results").replaceChildren();
  const source = names[$("try-source").value] || $("try-source").selectedOptions[0]?.textContent;
  const target = names[$("try-target").value] || $("try-target").selectedOptions[0]?.textContent;
  $("try-status").textContent = data.routes.length
    ? `Found ${data.routes.length} cited public path${data.routes.length === 1 ? "" : "s"} between ${source} and ${target}.`
    : (data.truncated ? `Search limit reached; no cited path found between ${source} and ${target} yet.`
      : `No cited public path connects ${source} and ${target} within six hops.`);
}
function renderDirectoryRows(container, people, category) {
  container.replaceChildren();
  if (!people.length) {
    container.append(node("p", category === "attendee"
      ? "No confirmed attendee list imported yet."
      : "No cited scheduled speakers listed yet.", "quiet-copy"));
    return;
  }
  for (const person of people) {
    const row = node("article", undefined, "directory-person");
    row.append(node("h3", person.name || person.id));
    if (person.overlap) row.append(node("p", category === "attendee"
      ? "Also listed as a scheduled speaker."
      : "Also listed as a confirmed attendee.", "directory-overlap"));
    if (category === "speaker") {
      for (const talk of person.talks || []) {
        row.append(node("p", talk.title || "Scheduled talk", "directory-talk"));
      }
    }
    for (const evidenceId of person.evidence_ids || []) {
      const source = evidence[evidenceId];
      if (source) row.append(sourceLink(source.url, source.claim || "Public source"));
    }
    container.append(row);
  }
}
async function loadConferenceContext() {
  const conferenceId = new URLSearchParams(window.location.search).get("conference");
  if (!conferenceId) return;
  const section = $("conference-context");
  section.hidden = false;
  try {
    const checkedJson = async response => {
      if (!response.ok) throw new Error("Conference request failed.");
      return response.json();
    };
    const [directory, peopleResponse] = await Promise.all([
      fetch("/api/conferences").then(checkedJson),
      fetch(`/api/conferences/${encodeURIComponent(conferenceId)}/people`).then(checkedJson)
    ]);
    Object.assign(evidence, peopleResponse.evidence || {});
    const conference = (directory.items || []).find(item => item.id === conferenceId);
    $("explore-conference-title").textContent = conference?.name || "Conference directory";
    $("explore-conference-dates").textContent = conference?.starts && conference?.ends
      ? `${conference.starts} – ${conference.ends}` : "Browse the public people listed for this conference.";
    renderDirectoryRows($("explore-attendees"), peopleResponse.confirmed_attendees || [], "attendee");
    renderDirectoryRows($("explore-speakers"), peopleResponse.scheduled_speakers || [], "speaker");
  } catch (_) {
    $("explore-conference-title").textContent = "Conference directory unavailable";
    $("explore-conference-dates").textContent = "Public profile exploration is still available below.";
    $("explore-attendees").replaceChildren(node("p", "Attendee information could not be loaded.", "quiet-copy"));
    $("explore-speakers").replaceChildren(node("p", "Speaker information could not be loaded.", "quiet-copy"));
  }
}
$("try-form").onsubmit = event => { event.preventDefault(); action("paths"); };
$("try-openers").onclick = () => action("openers");
$("try-example").onclick = () => {
  if (!example) return;
  $("try-source-filter").value = ""; $("try-target-filter").value = "";
  populateSelect("try-source", "try-source-filter");
  populateSelect("try-target", "try-target-filter");
  $("try-source").value = example.source; $("try-target").value = example.target;
  selectionChanged(); action("paths");
};
function selectionChanged() {
  $("try-path-results").replaceChildren();
  $("try-opener-results").replaceChildren();
  $("try-status").textContent = "Choose two distinct public profiles, then search.";
  controls();
}
$("try-source").onchange = selectionChanged;
$("try-target").onchange = selectionChanged;
$("try-source-filter").oninput = () => { populateSelect("try-source", "try-source-filter"); selectionChanged(); };
$("try-target-filter").oninput = () => { populateSelect("try-target", "try-target-filter"); selectionChanged(); };
async function init() {
  try {
    const response = await api("/api/try/people");
    people = response.items; example = response.example;
    for (const person of people) names[person.id] = person.name;
    populateSelect("try-source", "try-source-filter");
    populateSelect("try-target", "try-target-filter");
    const source = example?.source || people[0]?.id;
    const target = example?.target || people.find(person => person.id !== source)?.id;
    if (source) $("try-source").value = source;
    if (target) $("try-target").value = target;
    $("try-status").textContent = example ? "Try the cited example or choose two distinct public profiles."
      : (people.length ? "Choose two distinct public profiles." : "No public profiles are available.");
  } catch (error) { $("try-status").textContent = error.message; }
  controls();
}
init();
loadConferenceContext();
