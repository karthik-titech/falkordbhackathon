"use strict";
const $ = id => document.getElementById(id);
document.title = PRODUCT_NAME;
$("product-name").textContent = `${PRODUCT_NAME} · FalkorDB`;
let people = [], targets = [], requestId = null, requestRequester = null, requestState = null, revealed = false;
let names = {}, evidence = {}, polling = false, busy = false;
let scored = false, opened = false, animatedRoute = null;
const offers = new Map();
let panelSession = null, panelRevision = 0, panelPolling = null;
const CONFERENCE_NAMES = {
  aie_worldsfair_2026: "AI Engineer World's Fair 2026",
  github_universe_2026: "GitHub Universe 2026"
};

function conferenceName(id) {
  return Object.hasOwn(CONFERENCE_NAMES, id) ? CONFERENCE_NAMES[id] : id;
}

async function api(path, body, token) {
  const response = await fetch(path, body === undefined ? {headers: token ? {"X-Owner-Token": token} : {}} : {
    method: "POST", headers: {"Content-Type": "application/json", ...(token ? {"X-Owner-Token": token} : {})},
    ...(body === null ? {} : {body: JSON.stringify(body)})
  });
  const data = await response.json();
  if (data.mode === "recorded") $("mode-banner").hidden = false;
  if (!response.ok) throw new Error(data.error || "Request failed");
  Object.assign(names, data.people || {});
  Object.assign(evidence, data.evidence || {});
  return data;
}
function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  if (className) element.className = className;
  return element;
}
function sourceLink(url, label) {
  const element = node("a", label);
  try {
    const parsed = new URL(url);
    if (["https:", "http:"].includes(parsed.protocol)) {
      element.href = parsed.href; element.target = "_blank"; element.rel = "noopener noreferrer";
    }
  } catch (_) { /* A missing citation remains plain text. */ }
  return element;
}
function controls() {
  for (const id of ["ask", "score", "openers"]) $(id).disabled = busy || !requestId;
  $("send").disabled = busy || !["draft", "approved"].includes(requestState);
  $("find").disabled = busy || !$("requester").value || !$("target").value;
  $("log-meeting").disabled = busy || !$("requester").value || !$("meeting-person").value || !$("requester-token").value;
  for (const id of ["requester", "target", "goal", "target-filter", "meeting-filter", "meeting-person", "requester-token"]) $(id).disabled = busy;
  for (const button of document.querySelectorAll("[data-reveal]")) button.disabled = busy || revealed;
}
async function action(work) {
  if (busy) return;
  busy = true; controls();
  try { await work(); } catch (error) { $("status").textContent = error.message; }
  finally { busy = false; controls(); }
}
function svg(tag, attributes, text) {
  const element = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
  if (text !== undefined) element.textContent = text;
  return element;
}
function slide(data) {
  const steps = ["find", "ask", "approve", "score", "open"];
  const actions = new Set((data?.events || []).map(event => event.action));
  const request = data?.request;
  const step = !requestId ? "find" : opened || actions.has("openers_written") || requestState === "requested" ? "open" :
    scored || actions.has("fit_scored") ? "score" : revealed || (data?.routes.length && actions.has("reachability_asked")) ? "approve" : "ask";
  const current = steps.indexOf(step), number = String(current + 1).padStart(2, "0");
  for (const [index, item] of [...$("step-track").children].entries()) {
    item.classList.toggle("done", index < current);
    if (index === current) item.setAttribute("aria-current", "step");
    else item.removeAttribute("aria-current");
    item.querySelector(".step-marker").textContent = index <= current ? "■" : "□";
  }
  $("kicker").textContent = `◆ ${number} · ${step.toUpperCase()}`;
  $("step-counter").textContent = `${number} / 05`;
  const target = names[request?.target] || request?.target;
  const route = data?.revealed_route;
  const reachable = [...offers].find(([, answer]) => answer.status === "reachable");
  const ownerId = route?.persons[0] || reachable?.[0];
  const owner = ownerId && (names[ownerId] || ownerId);
  const headlines = {find: "Find your next conversation.", ask: `A warm path to ${target}.`,
    approve: owner ? `${owner} can reach ${target}.` : `A warm path to ${target}.`,
    score: `Your fit with ${target}.`, open: "Three ways to open."};
  $("headline").textContent = headlines[step];
  $("headline-detail").hidden = !owner || step !== "ask";
  $("headline-detail").textContent = owner ? `${owner} can reach them in ${route?.edges.length ?? reachable[1].hops} hops.` : "";
  const speaker = targets.find(person => person.id === request?.target), talk = speaker?.talks[0];
  $("subline").textContent = request ? [request.goal === "invest" ? "Invest" : "Product sales proposal", talk?.title, conferenceName(talk?.conference)].filter(Boolean).join(" · ") : "Choose a speaker and a goal.";
}
function draw(route, request) {
  const view = $("path-view"); view.replaceChildren(); $("hop-evidence").replaceChildren();
  const persons = route ? [...route.persons] : [request.requester, request.target];
  const asked = route?.route_id.startsWith("revealed") && persons[0] !== request.requester;
  // A revealed route begins at its owner. Show the requester as a separate starting node.
  if (persons[0] !== request.requester) persons.unshift(request.requester);
  const position = new Map(persons.map((id, index) => [id, 75 + index * 750 / Math.max(persons.length - 1, 1)]));
  const routeKey = `${request.id}:${route?.route_id}`;
  const animate = route?.route_id.startsWith("revealed") && animatedRoute !== routeKey;
  if (animate) animatedRoute = routeKey;
  const maskAttributes = animate && !matchMedia("(prefers-reduced-motion: reduce)").matches ? {mask: "url(#path-reveal)"} : {};
  if (maskAttributes.mask) {
    const defs = svg("defs", {}), mask = svg("mask", {id: "path-reveal", maskUnits: "userSpaceOnUse", x: 0, y: 0, width: 900, height: 220});
    mask.append(svg("line", {x1: 75, y1: 92, x2: 825, y2: 92, stroke: "white", "stroke-width": 16,
      pathLength: 1, "stroke-dasharray": 1, class: "route-span draw-in"}));
    defs.append(mask); view.append(defs);
  }
  if (asked) {
    const x1 = position.get(request.requester), x2 = position.get(persons[1]);
    view.append(svg("line", {x1, y1: 92, x2, y2: 92, class: "route-edge", "stroke-dasharray": "8 6", ...maskAttributes}));
    view.append(svg("text", {x: (x1 + x2) / 2, y: 125, class: "edge-label"}, "asked"));
  }
  for (const edge of route?.edges || []) {
    const x1 = position.get(edge.from), x2 = position.get(edge.to), item = evidence[edge.evidence_id];
    const label = edge.category === "met" && edge.from === request.requester ? "met · your graph" : edge.category;
    const group = svg("g", {});
    group.append(svg("line", {x1, y1: 92, x2, y2: 92, class: "route-edge", ...maskAttributes}),
      svg("text", {x: (x1 + x2) / 2, y: 125, class: "edge-label"}, label));
    const link = item && sourceLink(item.url, "source");
    if (link?.href) {
      const anchor = svg("a", {href: link.href, target: "_blank", rel: "noopener noreferrer", "aria-label": item.claim});
      anchor.append(group); view.append(anchor);
    } else view.append(group);
    const row = node("p", `${names[edge.from] || edge.from} → ${names[edge.to] || edge.to}: ${label}. `, "claim");
    row.append(item ? sourceLink(item.url, item.claim || "Public evidence") : node("span", "No public citation for this hop."));
    $("hop-evidence").append(row);
  }
  for (const id of persons) {
    const end = id === request.requester || id === request.target, size = end ? 32 : 12;
    view.append(svg("rect", {x: position.get(id) - size / 2, y: 92 - size / 2, width: size, height: size,
      class: end ? "route-node route-end" : "route-node"}));
    const label = names[id] || id;
    const words = label.split(/\s+/), lines = [""];
    for (const word of words) {
      if (lines[lines.length - 1].length + word.length > 16) lines.push("");
      lines[lines.length - 1] += (lines[lines.length - 1] ? " " : "") + word;
    }
    const text = svg("text", {x: position.get(id), y: 32, class: "route-label"});
    lines.forEach((line, i) => text.append(svg("tspan", {x: position.get(id), dy: i ? 19 : 0}, line)));
    view.append(text);
  }
  $("path-note").textContent = route ? (route.route_id.startsWith("revealed") ?
    "Approved owner route. The requester-to-owner connection is not a graph hop." :
    route.edges.some(edge => edge.category === "met") ? "Warm route using your graph. Select a cited edge to read its source." :
    "Best public route. Select an edge to read its source.") : "No warm route found. You can ask owners or approach directly.";
}
function ownersView() {
  $("owners").replaceChildren();
  for (const [owner, answer] of offers) {
    const label = `${names[owner] || owner} · ${answer.status === "reachable" ? `reachable · ${answer.hops} hops · tie ${answer.tie.toFixed(2)}` : answer.status.replaceAll("_", " ")}`;
    const row = node("div", undefined, "owner-row"); row.append(node("span", label));
    if (answer.status === "no_consent") row.append(node("span", "Ask the owner to approve, then press Ask owners again.", "claim"));
    if (answer.status === "reachable") {
      const button = node("button", "Reveal"); button.dataset.reveal = owner; button.disabled = revealed || busy;
      button.onclick = () => action(async () => {
        await api(`/api/requests/${requestId}/reveal`, {owner, offer_id: answer.offer_id});
        revealed = true; ownersView(); await refresh();
        $("status").textContent = "Route revealed with owner approval.";
      });
      row.append(button);
    }
    const link = node("a", "Open owner page"); link.href = `/owner?owner=${encodeURIComponent(owner)}`;
    link.target = "_blank"; link.rel = "noopener"; row.append(link);
    $("owners").append(row);
  }
}
function resetPanel() {
  panelSession = null; panelRevision++;
  $("panel-pending").replaceChildren();
  $("panel-open").disabled = !$("panel-owner").value || !$("panel-token").value;
  $("panel-status").textContent = "Choose an owner and enter their token.";
}
function restorePanelToken() {
  try { $("panel-token").value = sessionStorage.getItem(`warmopen-owner:${$("panel-owner").value}`) || ""; }
  catch (_) { $("panel-token").value = ""; }
  resetPanel();
}
function panelOwners(preferred) {
  const previous = $("panel-owner").value;
  const owners = people.filter(person => person.id !== $("requester").value);
  $("panel-owner").replaceChildren(...owners.map(person => new Option(person.name, person.id)));
  const selected = [panelSession ? previous : preferred, previous].find(id => owners.some(person => person.id === id));
  if (selected) $("panel-owner").value = selected;
  if (!panelSession && $("panel-owner").value !== previous) restorePanelToken();
  $("panel-open").disabled = !$("panel-owner").value || !$("panel-token").value;
}
async function panelPending() {
  const session = panelSession, revision = panelRevision;
  if (!session || session.granting || panelPolling === revision) return;
  panelPolling = revision;
  try {
    const data = await api(`/api/owner/${encodeURIComponent(session.owner)}/pending`, undefined, session.token);
    if (panelSession !== session || panelRevision !== revision) return;
    $("panel-pending").replaceChildren();
    for (const item of data.items) {
      const row = node("li");
      row.append(node("h3", `${item.requester_name} → ${item.target_name}`),
        node("p", item.goal === "invest" ? "Invest" : "Product sales proposal"));
      const actions = node("div", undefined, "actions");
      for (const [scope, label] of [["reachability", "Approve reachability"], ["reveal", "Approve reveal"]]) {
        const approved = `${scope === "reveal" ? "Reveal" : "Reachability"} approved`;
        const button = node("button", item[`${scope}_granted`] ? approved : label);
        button.type = "button"; button.dataset.scope = scope;
        button.disabled = item[`${scope}_granted`];
        button.onclick = async () => {
          if (panelSession !== session || session.granting || button.disabled) return;
          session.granting = true; panelRevision++;
          for (const control of $("panel-pending").querySelectorAll("button")) control.disabled = true;
          try {
            await api("/api/grants", {owner: session.owner, requester: item.requester,
              request_id: item.request_id, scope}, session.token);
            if (panelSession !== session) return;
            button.textContent = approved;
            $("status").textContent = "Owner approved. Press Ask owners again.";
            session.notice = "Owner approved. Press Ask owners again.";
          } catch (_) {
            session.notice = "Approval failed. Check the owner token and try again.";
          } finally {
            session.granting = false;
            if (panelSession === session) await panelPending();
          }
        };
        actions.append(button);
      }
      row.append(actions); $("panel-pending").append(row);
    }
    $("panel-status").textContent = session.notice || (data.items.length ? "Grants expire after 15 minutes." : "No requests yet. Press Ask owners on the left.");
  } catch (_) {
    if (panelSession === session && panelRevision === revision) {
      $("panel-pending").replaceChildren();
      $("panel-status").textContent = "Cannot load approvals. Check the owner token and try again.";
    }
  } finally { if (panelPolling === revision) panelPolling = null; }
}
$("panel-owner").onchange = restorePanelToken;
$("panel-token").oninput = resetPanel;
$("panel-form").onsubmit = event => {
  event.preventDefault(); resetPanel();
  const owner = $("panel-owner").value, token = $("panel-token").value;
  if (!owner || !token) return;
  try { sessionStorage.setItem(`warmopen-owner:${owner}`, token); }
  catch (_) { /* The token stays in this page's memory. */ }
  panelSession = {owner, token, granting: false};
  $("panel-status").textContent = "Loading approvals…";
  panelPending();
};
setInterval(panelPending, 2000);
async function refresh() {
  const rid = requestId;
  if (!rid) return;
  const data = await api(`/api/requests/${rid}`, undefined, requesterToken());
  if (rid !== requestId) return;
  requestState = data.request.state; revealed = !!data.revealed_route;
  $("request-state").textContent = requestState.replaceAll("_", " ");
  draw(data.revealed_route || data.routes[0], data.request);
  $("memory-note").hidden = !data.request.use_own_memory;
  $("agent-timeline").replaceChildren(...data.events.map(event => node("li", `${event.agent}: ${event.action}`)));
  slide(data);
  controls();
}
function filterTargets() {
  const previous = $("target").value, term = $("target-filter").value.toLowerCase();
  const filtered = targets.filter(target => [target.name, ...target.talks.flatMap(talk => [talk.title, talk.conference, conferenceName(talk.conference)])].join(" ").toLowerCase().includes(term));
  $("target").replaceChildren(...filtered.map(target => new Option(target.name, target.id)));
  if (filtered.some(target => target.id === previous)) $("target").value = previous;
  controls();
}
$("target-filter").oninput = filterTargets;
function filterMeetings() {
  const previous = $("meeting-person").value, term = $("meeting-filter").value.toLowerCase();
  const candidates = [...new Map([...people, ...targets].map(person => [person.id, person])).values()]
    .filter(person => person.id !== $("requester").value && person.name.toLowerCase().includes(term))
    .sort((a, b) => a.name.localeCompare(b.name));
  $("meeting-person").replaceChildren(...candidates.map(person => new Option(person.name, person.id)));
  if (candidates.some(person => person.id === previous)) $("meeting-person").value = previous;
  controls();
}
function tokenKey() { return `warmopen:requester-token:${$("requester").value}`; }
function requesterToken() { return sessionStorage.getItem(`warmopen:requester-token:${requestRequester}`) || ""; }
function selectRequester() {
  resetPanel();
  $("requester-token").value = sessionStorage.getItem(tokenKey()) || "";
  $("meeting-status").textContent = "";
  filterMeetings();
  panelOwners();
}
$("requester-token").oninput = () => {
  if ($("requester-token").value) sessionStorage.setItem(tokenKey(), $("requester-token").value);
  else sessionStorage.removeItem(tokenKey());
  controls();
};
$("meeting-filter").oninput = filterMeetings;
$("meeting-person").onchange = controls;
$("requester").onchange = selectRequester;
$("target").onchange = controls;
async function findPath() {
  const requester = $("requester").value;
  const data = await api("/api/requests", {requester, target: $("target").value, goal: $("goal").value}, $("requester-token").value);
  requestRequester = requester;
  requestId = data.request_id; requestState = data.state; revealed = false; offers.clear(); ownersView();
  scored = false; opened = false; animatedRoute = null;
  $("fit").textContent = "Ready to score."; $("opener-cards").replaceChildren();
  await refresh();
}
$("find-form").onsubmit = event => {
  event.preventDefault(); action(async () => {
    await findPath(); $("status").textContent = "Path search complete.";
  });
};
$("meeting-form").onsubmit = event => {
  event.preventDefault(); action(async () => {
    const person = $("meeting-person").value;
    await api("/api/meetings", {requester: $("requester").value, person}, $("requester-token").value);
    $("meeting-status").textContent = `Logged: you met ${names[person] || person}. Find a path again to use it.`;
    if ($("target").value) {
      await findPath(); $("status").textContent = "Path search complete.";
    }
  });
};
$("ask").onclick = () => action(async () => {
  // Read the request identity, since picker choices can change after a request was created.
  const view = await api(`/api/requests/${requestId}`, undefined, requesterToken());
  for (const person of people.filter(person => person.id !== view.request.requester)) {
    offers.set(person.id, await api(`/api/requests/${requestId}/reachability`, {owner: person.id}));
    ownersView();
  }
  panelOwners([...offers].find(([, answer]) => ["no_consent", "reachable"].includes(answer.status))?.[0]);
  await refresh(); $("status").textContent = "Owners asked. After approval, press Ask owners again.";
});
$("score").onclick = () => action(async () => {
  const fit = await api(`/api/requests/${requestId}/score`, null, requesterToken()), card = $("fit"); card.replaceChildren();
  scored = true;
  const abstentionMessages = {
    insufficient_evidence: "Not enough public evidence to score.",
    low_confidence: "The decision model was not confident enough to score.",
    jev_unavailable: "Scoring service unavailable. Showing graph reasons only."
  };
  card.append(node("p", fit.abstained ? abstentionMessages[fit.reason] : `${fit.band} · ${fit.value}`, "metric"));
  if (!fit.abstained) card.append(node("p", `Confidence: ${fit.confidence ?? "unavailable"}`));
  const via = fit.introducer?.via;
  card.append(node("p", `Introducer: ${via ? (names[via] || via) : (fit.introducer?.route_id || "unavailable")}`));
  for (const [key, title] of [["next_action", "Suggested move"], ["cue_type", "Opener style"]]) {
    const move = fit.move?.[key];
    card.append(node("p", move ? `${title}: ${move.choice.replaceAll("_", " ")} · Confidence: ${move.confidence}` :
      (key === "next_action" ? "No suggested move" : "Opener style: unavailable")));
  }
  const reasons = node("div", undefined, "fit-reasons");
  for (const [key, title, marker] of [["supports", "Supports", "■"], ["against", "Against", "◩"], ["would_improve", "Would improve", "□"]]) {
    const column = node("section", undefined, key), heading = node("h3");
    const square = node("span", marker, "reason-marker"); square.setAttribute("aria-hidden", "true");
    heading.append(square, document.createTextNode(title)); column.append(heading);
    for (const item of fit[key]) {
      const row = node("p", item.text + " "), cited = evidence[item.evidence_id];
      if (cited) row.append(sourceLink(cited.url, "Source"));
      column.append(row);
    }
    if (!fit[key].length) column.append(node("p", "None recorded."));
    reasons.append(column);
  }
  card.append(reasons);
  await refresh(); $("status").textContent = "Fit assessment complete.";
});
$("openers").onclick = () => action(async () => {
  const data = await api(`/api/requests/${requestId}/openers`, null, requesterToken()); $("opener-cards").replaceChildren();
  opened = true;
  for (const item of data.items) {
    const card = node("article", undefined, "cue"), cited = evidence[item.evidence_id];
    card.append(node("p", `“${item.text}”`));
    if (cited) card.append(sourceLink(cited.url, "Source"), node("p", cited.claim, "claim"));
    else card.append(node("p", "No source: general opener", "claim"));
    $("opener-cards").append(card);
  }
  await refresh(); $("status").textContent = "Three opener cues ready.";
});
$("send").onclick = () => action(async () => {
  const data = await api(`/api/requests/${requestId}/send`, null);
  requestState = data.state; await refresh(); $("status").textContent = "Intro request recorded.";
});
async function init() {
  try {
    people = (await api("/api/people")).items;
    targets = (await api("/api/targets")).items;
    for (const person of [...people, ...targets]) names[person.id] = person.name;
    $("requester").replaceChildren(...people.map(person => new Option(person.name, person.id)));
    filterTargets();
    selectRequester();
    $("status").textContent = people.length ? "Choose a speaker and goal." : "No consented attendees loaded. Load the curated demo seed first.";
  } catch (error) { $("status").textContent = error.message; }
  controls();
  slide();
}
setInterval(async () => {
  if (!requestId || busy || polling) return;
  polling = true;
  try { await refresh(); } catch (error) { $("status").textContent = error.message; }
  finally { polling = false; }
}, 2000);
init();
