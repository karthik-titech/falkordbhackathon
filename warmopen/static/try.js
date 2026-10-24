"use strict";
const $ = id => document.getElementById(id);
document.title = `${PRODUCT_NAME} · Find your next conversation`;
$("try-product-name").textContent = PRODUCT_NAME;
let people = [], names = {}, evidence = {}, example = null, busy = false;
let conferenceRoster = {}, conferenceGraph = null, defaultGraphFocus = "", graphZoom = 1, graphRequestToken = 0;
let graphYaw = -0.35, graphPitch = 0.28, graphPointer = null, suppressGraphClick = false;
let conferenceTopics = [], interestTopicIds = new Set(), seekingTopicIds = new Set(), profileTopicContext = null;
let conversationResults = new Map(), conversationBusy = false;
let peopleMatchesKey = "", peopleMatchesRequest = 0, initialRecommendationChosen = false, targetChosenByUser = false;
let peopleMatchScores = new Map();
const DEFAULT_CATEGORY_SCORES = {mirror: 30, missing_piece: 25, unexpected_connection: 20};

const SVG_NS = "http://www.w3.org/2000/svg";
const GRAPH_LIMIT = 48;
const GRAPH_CATEGORIES = new Set(["shared_work", "co_speaker", "coauthor"]);
const PROFILE_CONTEXT_KEY = "warmopen_profile_context_v1";

function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  if (className) element.className = className;
  return element;
}
function sourceLink(url, label) {
  const link = node("a", label);
  const href = safeHttpUrl(url);
  if (href) { link.href = href; link.target = "_blank"; link.rel = "noopener noreferrer"; }
  return link;
}
function safeHttpUrl(url) {
  try {
    const parsed = new URL(url);
    if (["https:", "http:"].includes(parsed.protocol)) return parsed.href;
  } catch (_) { /* Keep malformed sources as plain text. */ }
  return null;
}
function svgElement(tag, attributes = {}, text) {
  const element = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, String(value));
  if (text !== undefined) element.textContent = text;
  return element;
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
    row.append(node("h3", person.name || "Unnamed public profile"));
    if (person.overlap) row.append(node("p", category === "attendee"
      ? "Also listed as a scheduled speaker."
      : "Also listed as a confirmed attendee.", "directory-overlap"));
    if (category === "speaker") {
      for (const talk of person.talks || []) {
        row.append(node("p", talk.title || "Scheduled talk", "directory-talk"));
      }
    }
    for (const [index, evidenceId] of (person.evidence_ids || []).entries()) {
      const source = evidence[evidenceId];
      if (source && safeHttpUrl(source.url)) row.append(sourceLink(source.url, `Source ${index + 1}`));
    }
    container.append(row);
  }
}

function graphRoles(roles) {
  const values = Array.isArray(roles) ? roles : [];
  return {
    attendee: values.includes("confirmed_attendee"),
    speaker: values.includes("scheduled_speaker"),
  };
}
function graphRoleLabel(roles) {
  const {attendee, speaker} = graphRoles(roles);
  if (attendee && speaker) return "Confirmed attendee and scheduled speaker";
  if (attendee) return "Confirmed attendee";
  if (speaker) return "Scheduled speaker";
  return "Public profile";
}
function graphDistanceLabel(distance, isCenter) {
  if (isCenter) return "Focused profile";
  if (distance === null) return "No supported path in this view";
  return `${distance} ${distance === 1 ? "link" : "links"} from the focus`;
}
function textShort(name, limit = 14) {
  const characters = Array.from(name || "");
  return characters.length > limit ? characters.slice(0, limit).join("") + "…" : (name || "Public profile");
}
function edgeHasPublicCitation(edge) {
  if (!GRAPH_CATEGORIES.has(edge.category) || !Array.isArray(edge.evidence_ids)) return false;
  return edge.evidence_ids.some(id => evidence[id] && safeHttpUrl(evidence[id].url));
}
function renderGraphDetail(personId) {
  const container = $("graph-person-detail");
  container.replaceChildren();
  const graphNode = conferenceGraph?.nodes.find(item => item.id === personId);
  if (!graphNode) {
    container.append(node("h2", "Select a profile"),
      node("p", "Focus a public profile to inspect its conference role and sources.", "quiet-copy"));
    return;
  }
  const roles = graphRoles(graphNode.roles);
  const rosterPerson = conferenceRoster[personId] || {};
  const initials = graphNode.name.trim().split(/\s+/).slice(0, 2).map(part => part[0]).join("");
  container.append(node("div", initials, "person-avatar"));
  const comparisonId = graphSourceId();
  const comparisonName = conferenceRoster[comparisonId]?.name || names[comparisonId];
  container.append(node("p", comparisonName ? `MATCHING FROM ${comparisonName}` : "YOUR NEXT CONVERSATION", "graph-detail-kicker"));
  container.append(node("h2", graphNode.name));
  const roleLabels = [];
  if (roles.attendee) roleLabels.push("Confirmed attendee");
  if (roles.speaker) roleLabels.push("Scheduled speaker");
  container.append(node("p", roleLabels.join(" · ") || "Public conference profile", "graph-detail-role"));
  const researchLabels = {complete: "Individual professional bio researched", conference_only: "Conference sources researched · individual bio still needed", unavailable: "Profile research unavailable"};
  if (researchLabels[graphNode.research_status]) container.append(node("p", researchLabels[graphNode.research_status], "graph-profile-research-status"));

  const categories = {
    mirror: {label: "Mirror", className: "graph-category-mirror"},
    missing_piece: {label: "Missing piece", className: "graph-category-missing"},
    unexpected_connection: {label: "Unexpected connection", className: "graph-category-unexpected"},
  };
  const comparison = Object.prototype.hasOwnProperty.call(categories, graphNode.connection_type)
    ? categories[graphNode.connection_type] : {label: "Add interests to personalize", className: "graph-category-unknown"};
  if (Object.prototype.hasOwnProperty.call(categories, graphNode.connection_type)) container.append(node("p", comparison.label, `graph-category-badge ${comparison.className}`));
  const categoryReasons = {
    mirror: "Shares a cited public topic or work signal with the selected profile.",
    missing_piece: "Has cited evidence about a topic the selected profile is looking for.",
    unexpected_connection: "A cited public relationship path connects this profile to the selected profile.",
  };
  const reason = typeof graphNode.reason === "string" && graphNode.reason.length <= 240
    ? graphNode.reason : (categoryReasons[graphNode.connection_type]
      || "Not enough supported public context to compare this profile yet.");
  if (Object.prototype.hasOwnProperty.call(categories, graphNode.connection_type)) container.append(node("p", reason, "graph-detail-reason"));
  const sourceId = graphSourceId();
  const sourceName = names[sourceId] || $("try-source").selectedOptions[0]?.textContent;
  const background = node("details", undefined, "person-background");
  background.append(node("summary", "Talks & public sources"));
  const backgroundContent = node("div");
  backgroundContent.append(node("p", sourceId && sourceName
    ? `Comparing with ${sourceName}. This does not identify you.`
    : "No conference profile is treated as you.", "graph-comparison-note"));
  const supportedTopics = Array.isArray(graphNode.topics) ? graphNode.topics : [];
  if (supportedTopics.length) {
    const attribution = node("div", undefined, "person-topics");
    attribution.append(node("p", "Topics from public work", "person-topics-heading"));
    for (const topic of supportedTopics.slice(0, 10)) {
      const chip = node("span", topic.name || topic.id, "person-topic-chip");
      chip.title = "Inferred from cited professional work; not a claim about private interests.";
      attribution.append(chip);
    }
    container.append(attribution);
  }
  renderConversationPanel(container, personId);

  const talks = Array.isArray(rosterPerson.talks) ? rosterPerson.talks : [];
  if (talks.length) {
    backgroundContent.append(node("h3", "Scheduled talks"));
    const list = node("ul", undefined, "graph-talk-list");
    for (const talk of talks.filter((talk, index, all) => all.findIndex(other => other.title === talk.title) === index).slice(0, 4)) {
      const item = node("li");
      item.append(document.createTextNode(talk.title || "Scheduled talk"));
      const sourceId = (rosterPerson.evidence_ids || []).find(id => evidence[id] && safeHttpUrl(evidence[id].url));
      if (sourceId) item.append(document.createTextNode(" · "), sourceLink(evidence[sourceId].url, "Source"));
      list.append(item);
    }
    backgroundContent.append(list);
  }

  const sourceIds = new Set(rosterPerson.evidence_ids || []);
  for (const evidenceId of graphNode.context_evidence_ids || []) sourceIds.add(evidenceId);
  for (const edge of conferenceGraph.edges || []) {
    if (edge.source === personId || edge.target === personId) {
      for (const evidenceId of edge.evidence_ids || []) sourceIds.add(evidenceId);
    }
  }
  const sources = Array.from(sourceIds).filter(id => evidence[id] && safeHttpUrl(evidence[id].url)).slice(0, 8);
  backgroundContent.append(node("h3", "Public sources"));
  if (sources.length) {
    const list = node("ul", undefined, "graph-source-list");
    for (const [index, evidenceId] of sources.entries()) {
      const item = node("li");
      item.append(sourceLink(evidence[evidenceId].url, `Source ${index + 1}`));
      list.append(item);
    }
    backgroundContent.append(list);
  } else {
    backgroundContent.append(node("p", "No public source links are available in this view.", "quiet-copy"));
  }
  background.append(backgroundContent);
  container.append(background);
}

function matchContext() {
  return {source: graphSourceId(), interest_topic_ids: Array.from(interestTopicIds).sort(),
    seeking_topic_ids: Array.from(seekingTopicIds).sort()};
}
function invalidateMatchViews() {
  if (!targetChosenByUser) initialRecommendationChosen = false;
  peopleMatchesRequest += 1;
  peopleMatchesKey = "";
  conversationResults.clear();
  peopleMatchScores.clear();
  if (conferenceGraph) renderGraphDetail(conferenceGraph.center_id);
  for (const prefix of ["mirror", "missing", "unexpected"]) {
    $(`${prefix}-count`).textContent = "…";
    $(`${prefix}-people`).replaceChildren(node("p", "Updating for your current interests and starting profile…", "people-match-empty"));
  }
  loadPeopleMatches();
}
function conversationKey(targetId) {
  return JSON.stringify([targetId, matchContext()]);
}

function confidenceCopy(value) {
  return typeNumber(value) && value >= 0 && value <= 1
    ? `Confidence: ${Math.round(value * 100)}%` : "Confidence unavailable";
}
function typeNumber(value) {
  return typeof value === "number" && Number.isFinite(value);
}
function renderConversationPanel(container, targetId) {
  const panel = node("section", undefined, "graph-conversation-panel");
  panel.append(node("h3", "Make the first move"));
  panel.append(node("p", "A little context. A more natural hello.", "conversation-hint"));
  const key = conversationKey(targetId), result = conversationResults.get(key);
  const actions = node("div", undefined, "graph-conversation-actions");
  const research = node("button", "Help me start a conversation", "graph-action-button graph-action-primary");
  const sourceId = graphSourceId();
  const sameSourceTarget = Boolean(sourceId && sourceId === targetId);
  research.disabled = sameSourceTarget || conversationBusy;
  research.setAttribute("type", "button");
  if (result) research.textContent = "Refresh conversation ideas ↻";
  research.addEventListener("click", () => assessConversation(targetId, true));
  actions.append(research);
  panel.append(actions);
  const interestsLink = node("button", interestTopicIds.size || seekingTopicIds.size
    ? "Adjust interests for more personal suggestions" : "Add interests for more personal suggestions", "graph-interests-link");
  interestsLink.type = "button";
  interestsLink.addEventListener("click", () => {
    const details = $("graph-topic-picker");
    details.open = true;
    details.scrollIntoView({behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth", block: "center"});
    details.querySelector("summary")?.focus();
  });
  panel.append(interestsLink);

  const status = node("p", "", "graph-action-status");
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");
  panel.append(status);
  if (result) renderConversationResult(panel, result);
  container.append(panel);
}
function renderConversationResult(container, data) {
  const assessment = data.assessment || {};
  const modelScore = boundedScore(assessment.score);
  const roughScore = boundedScore(assessment.rough_score);
  const useRoughScore = modelScore === null && roughScore !== null;
  const warm = (Array.isArray(data.ranked_openers) ? data.ranked_openers : []).find(item => item.mutual_name);
  const warmStatus = node("details", undefined, "warm-intro-status");
  warmStatus.append(node("summary", warm ? `Warm intro available · via ${warm.mutual_name}` : "Warm intro · no shared person verified yet"));
  warmStatus.append(node("p", warm
    ? "The shared-person opener is shown first, with citations for both sides of the public-work connection."
    : (data.source ? "No fully cited two-hop connection through the same person was found for this pair."
      : "Your profile links supply professional interests, not a verified contacts list. A personal mutual contact has not been established.")));
  container.append(warmStatus);
  renderOpeningLines(container, data.ranked_openers);
  renderNextActions(container, data);
  const match = node("section", undefined, "graph-match-summary");
  match.append(node("h3", "Why this person"));
  const matchLabels = {mirror: "Mirror", missing_piece: "Missing piece",
    unexpected_connection: "Unexpected connection"};
  const matchType = matchLabels[data.connection_type] ? data.connection_type : null;
  const matchClass = {mirror: "mirror", missing_piece: "missing", unexpected_connection: "unexpected"};
  match.append(node("span", matchType ? matchLabels[matchType] : "Add interests to personalize",
    `graph-category-badge ${matchType ? `graph-category-${matchClass[matchType]}` : "graph-category-unknown"}`));
  const displayedScore = modelScore === null ? roughScore : modelScore;
  if (useRoughScore) {
    match.append(node("span", "Uncalibrated fit · starting estimate", "graph-estimate-pill"));
    match.append(node("span", `~${Math.round(roughScore)}/100`, "graph-inline-score graph-inline-estimate"));
    match.append(node("p", "Based on limited conference information.", "graph-estimate-note"));
  } else if (displayedScore !== null) {
    match.append(node("span", `Uncalibrated fit ${Math.round(displayedScore)}/100`, "graph-inline-score"));
  } else {
    match.append(node("span", "No estimate available", "graph-inline-score graph-inline-estimate"));
  }
  const confidence = typeNumber(assessment.model_confidence)
    && assessment.model_confidence >= 0 && assessment.model_confidence <= 1
    ? confidenceCopy(assessment.model_confidence)
    : (useRoughScore ? "Model confidence unavailable; this is a rough starting estimate."
      : "Model confidence unavailable.");
  match.append(node("p", confidence, "graph-result-confidence"));
  if (typeof data.reason === "string" && data.reason.trim()) {
    match.append(node("p", data.reason.trim().slice(0, 180), "graph-match-reason"));
  }
  container.append(match);
  if (Array.isArray(data.categories) && data.categories.length) {
    const details = node("details", undefined, "graph-match-details");
    details.append(node("summary", "See match details"));
    const list = node("div", undefined, "graph-category-list");
    for (const [index, category] of data.categories.slice(0, 3).entries()) {
      const row = node("article", undefined, "graph-category-row");
      const type = ["mirror", "missing_piece", "unexpected_connection"].includes(category.type)
        ? category.type : "unknown";
      const labels = {mirror: "Mirror", missing_piece: "Missing piece",
        unexpected_connection: "Unexpected connection", unknown: "Needs context"};
      const title = node("span", `${index + 1}. ${labels[type]}`, "graph-category-title");
      const categoryModelScore = boundedScore(category.score);
      const sharedStartingScore = peopleMatchScores.get(`${data.target}:${type}`);
      const categoryRoughScore = boundedScore(sharedStartingScore === undefined ? category.rough_score : sharedStartingScore);
      const categoryScore = categoryModelScore === null ? categoryRoughScore : categoryModelScore;
      const useDefault = (category.supported === false && sharedStartingScore === undefined) || categoryScore === null || categoryScore <= 0;
      const shownScore = useDefault ? (DEFAULT_CATEGORY_SCORES[type] || 20) : Math.round(categoryScore);
      const scoreText = `${useDefault || categoryModelScore === null ? "~" : ""}${shownScore}/100`;
      row.append(title, node("span", scoreText, "graph-category-score"));
      if (useDefault) row.append(node("p", "Default starting estimate · add profile interests to personalize.", "graph-category-reason"));
      const reason = Array.isArray(category.reasons)
        ? category.reasons.find(item => typeof item === "string" && item.trim()
          && item.trim().toLowerCase() !== "needs context.") : null;
      if (reason && !useDefault) row.append(node("p", reason.trim().slice(0, 180), "graph-category-reason"));
      list.append(row);
    }
    details.append(list);
    container.append(details);
  }
  const evidenceIds = data.context && Array.isArray(data.context.evidence_ids) ? data.context.evidence_ids : [];
  const contextSources = evidenceIds.filter(id => evidence[id] && safeHttpUrl(evidence[id].url)).slice(0, 6);
  if (contextSources.length) {
    const links = node("details", undefined, "graph-context-sources");
    links.append(node("summary", "Public evidence"));
    for (const [index, id] of contextSources.entries()) {
      const row = node("p", undefined, "graph-evidence-source");
      row.append(sourceLink(evidence[id].url, `Source ${index + 1}`));
      if (typeof evidence[id].claim === "string") row.append(document.createTextNode(` · ${evidence[id].claim.slice(0, 200)}`));
      links.append(row);
    }
    container.append(links);
  }
  if (data.mentions && typeof data.mentions === "object") renderMentions(container, data.mentions);
  const refresh = data.refresh || {};
  const statuses = {not_requested: "Public context was not refreshed.", unavailable: "Public context refresh is unavailable.",
    ok: "Public context was refreshed.", failed: "Public context could not be refreshed."};
  if (refresh.status && refresh.status !== "not_requested") {
    container.append(node("p", statuses[refresh.status] || "Public context refresh status is unknown.", "graph-refresh-status"));
  }
}
function renderNextActions(container, data) {
  const targetName = names[data.target] || conferenceGraph?.nodes?.find(person => person.id === data.target)?.name || "";
  const firstName = targetName.split(" ")[0] || "there";
  const opener = data.ranked_openers?.find(item => typeof item.text === "string")?.text || "What are you working on right now?";
  const section = node("section", undefined, "next-actions");
  section.append(node("h3", "Keep the conversation going"));
  const draft = node("textarea", undefined, "followup-draft");
  draft.setAttribute("aria-label", "Edit your follow-up message");
  draft.rows = 4;
  draft.value = `Hi ${firstName}! ${opener.replace(/^Hey(?: [^,]+)?,\s*/i, "")} Would you be open to connecting?`;
  section.append(draft);
  const actions = node("div", undefined, "followup-actions");
  const linkedin = $("linkedin-followup-link").content.firstElementChild.cloneNode(true);
  const linkedinUrl = new URL(linkedin.href);
  linkedinUrl.searchParams.set("keywords", targetName);
  linkedin.href = linkedinUrl.href;
  linkedin.className = "followup-action";
  const email = node("a", "Draft email", "followup-action");
  const text = node("a", "Draft text", "followup-action");
  const updateLinks = () => {
    email.href = `mailto:?subject=${encodeURIComponent("Let's connect after the conference")}&body=${encodeURIComponent(draft.value)}`;
    text.href = `sms:?body=${encodeURIComponent(draft.value)}`;
  };
  draft.addEventListener("input", updateLinks);
  updateLinks();
  const copy = node("button", "Copy message", "followup-action");
  copy.type = "button";
  copy.addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(draft.value); copy.textContent = "Copied ✓"; }
    catch (_) { draft.focus(); draft.select(); copy.textContent = "Message selected"; }
  });
  actions.append(linkedin, email, text, copy);
  section.append(actions, node("p", "Review the message and choose a recipient in LinkedIn, your email app, or Messages. Nothing is sent automatically.", "followup-note"));
  container.append(section);
}
function boundedScore(value) {
  return typeNumber(value) && value >= 0 && value <= 100 ? value : null;
}
function renderOpeningLines(container, rankedOpeners) {
  const fallback = [
    "What are you hoping to learn or discuss at this conference?",
    "Which session or topic has caught your attention so far?",
    "What would make this conference especially useful for you?",
  ];
  const openers = Array.isArray(rankedOpeners) ? rankedOpeners.slice()
    .filter(item => item && typeof item.text === "string" && item.text.trim())
    .sort((left, right) => (Number.isInteger(left.rank) ? left.rank : 99)
      - (Number.isInteger(right.rank) ? right.rank : 99)).slice(0, 3) : [];
  const displayItems = openers.length ? openers : fallback.map((text, index) => ({text, rank: index + 1}));
  container.append(node("h3", "Try saying…"));
  const list = node("div", undefined, "graph-opening-list");
  displayItems.forEach((item, index) => {
    const card = node("article", undefined, `graph-opener-card${index === 0 ? " graph-opener-featured" : ""}`);
    const rank = Number.isInteger(item.rank) && item.rank > 0 ? item.rank : index + 1;
    card.append(node("span", String(rank).padStart(2, "0"), "graph-opener-rank"));
    if (typeof item.mutual_name === "string" && item.mutual_name.trim()) {
      card.append(node("span", `Warm intro · shared connection through ${item.mutual_name.trim()}`, "opener-mutual"));
    }
    card.append(node("p", item.text.trim(), "graph-opener-text"));
    const sourceIds = Array.from(new Set([item.evidence_id,
      ...(Array.isArray(item.evidence_ids) ? item.evidence_ids : [])]))
      .filter(id => typeof id === "string" && evidence[id] && safeHttpUrl(evidence[id].url)).slice(0, 4);
    if (sourceIds.length) {
      const fact = node("details", undefined, "graph-opener-source");
      fact.append(node("summary", sourceIds.length > 1 ? "See the connection sources" : "Based on public source"));
      for (const [index, id] of sourceIds.entries()) {
        const cited = evidence[id];
        fact.append(sourceLink(cited.url, sourceIds.length > 1 ? `Source ${index + 1}` : "View source"),
          node("p", cited.claim || "Public source fact", "graph-opener-fact"));
      }
      card.append(fact);
    }
    const copy = node("button", "Copy opening line", "opener-copy");
    copy.type = "button";
    copy.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(item.text.trim());
        copy.textContent = "Copied ✓";
      } catch (_) {
        copy.textContent = "Select the text to copy";
      }
    });
    card.append(copy);
    list.append(card);
  });
  container.append(list);
}
function renderMentions(container, mentions) {
  const details = node("details", undefined, "graph-mentions");
  details.append(node("summary", "Public professional mentions"));
  details.append(node("p", "Tone describes the post, not a verified fact about the person.", "graph-mentions-caveat"));
  const items = Array.isArray(mentions.items) ? mentions.items.filter(item => item
    && typeof item === "object" && typeof item.url === "string") : [];
  if (!items.length) {
    const notRequested = mentions.status === "not_requested";
    const successfulEmpty = ["complete", "ok", "no_results", "empty"].includes(mentions.status);
    details.append(node("p", notRequested
      ? "Mention search runs when you choose Help me start a conversation."
      : (successfulEmpty ? "No public professional mentions were found for this search."
        : "Mention search is not available right now."), "graph-mentions-empty"));
    container.append(details);
    return;
  }
  const platformLabels = {x: "X", linkedin: "LinkedIn"};
  const toneLabels = {positive: "Positive", neutral: "Neutral", critical: "Critical", unclear: "Unclear"};
  for (const item of items.slice(0, 8)) {
    const article = node("article", undefined, "graph-mention-item");
    const title = typeof item.title === "string" && item.title.trim()
      ? item.title.trim().slice(0, 240) : "Public professional post";
    article.append(node("h4", title));
    const meta = node("p", undefined, "graph-mention-meta");
    const platform = platformLabels[item.platform] || "Public source";
    meta.append(node("span", platform));
    if (typeof item.published_at === "string" && item.published_at.trim()) {
      meta.append(document.createTextNode(` · ${item.published_at.trim().slice(0, 64)}`));
    }
    const tone = Object.prototype.hasOwnProperty.call(toneLabels, item.tone) ? item.tone : "unclear";
    meta.append(document.createTextNode(" · "), node("span", `Post tone: ${toneLabels[tone]}`, `graph-mention-tone graph-mention-tone-${tone}`));
    article.append(meta);
    if (typeof item.excerpt === "string" && item.excerpt.trim()) {
      article.append(node("p", item.excerpt.trim().slice(0, 1200), "graph-mention-excerpt"));
    }
    const href = safeHttpUrl(item.url);
    if (href) article.append(sourceLink(href, `${platform} source`));
    else article.append(node("span", "Source link unavailable.", "quiet-copy"));
    details.append(article);
  }
  container.append(details);
}
async function assessConversation(targetId, refresh) {
  const sourceId = graphSourceId();
  const conferenceId = new URLSearchParams(window.location.search).get("conference");
  if ((sourceId && sourceId === targetId) || !conferenceId || conversationBusy) return;
  conversationBusy = true;
  const requestKey = conversationKey(targetId);
  const context = matchContext();
  const requestedInterests = context.interest_topic_ids;
  const requestedSeeking = context.seeking_topic_ids;
  const requestIsCurrent = () => requestKey === conversationKey(targetId)
    && conferenceGraph?.center_id === targetId && $("graph-focus").value === targetId;
  const status = $("graph-person-detail").querySelector(".graph-action-status");
  if (status) status.textContent = "Finding a good way to say hello…";
  const busyButton = $("graph-person-detail").querySelector(".graph-action-primary");
  if (busyButton) busyButton.textContent = "Preparing your opening lines…";
  $("graph-person-detail").querySelectorAll(".graph-action-button").forEach(button => { button.disabled = true; });
  const body = {
    target: targetId,
    refresh,
    interest_topic_ids: requestedInterests,
    seeking_topic_ids: requestedSeeking,
  };
  if (sourceId) body.source = sourceId;
  let failed = false;
  try {
    const response = await fetch(`/api/conferences/${encodeURIComponent(conferenceId)}/conversation`, {
      method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body),
    });
    if (!response.ok) throw new Error("Conversation assessment unavailable");
    const data = await response.json();
    Object.assign(evidence, data.evidence || {});
    conversationResults.set(requestKey, data);
    if (requestIsCurrent()) {
      const graphNode = conferenceGraph?.nodes.find(item => item.id === targetId);
      if (graphNode) {
        graphNode.connection_type = data.connection_type;
        graphNode.reason = data.reason;
        graphNode.reason_code = data.reason_code;
        graphNode.context_evidence_ids = data.context?.evidence_ids || [];
      }
    }
  } catch (_) {
    failed = requestIsCurrent();
  } finally {
    conversationBusy = false;
    if (conferenceGraph) renderConferenceGraph();
    if (failed) {
      const currentStatus = $("graph-person-detail").querySelector(".graph-action-status");
      if (currentStatus) currentStatus.textContent = "Could not retrieve public conversation context. Try again or continue browsing.";
    }
  }
}
function graphPositions(graph, use3D = $("graph-3d-toggle").checked) {
  const centerX = 260, centerY = 260, positions = new Map();
  const center = graph.nodes.find(item => item.id === graph.center_id);
  if (center) positions.set(center.id, {x: centerX, y: centerY, distance: 0, z: 0, scale: 1});
  const groups = new Map();
  for (const item of graph.nodes) {
    if (item.id === graph.center_id) continue;
    const distance = Number.isInteger(item.distance) && item.distance >= 1 && item.distance <= 6
      ? item.distance : null;
    const key = distance === null ? "outer" : String(distance);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(item);
  }
  const cosineYaw = Math.cos(graphYaw), sineYaw = Math.sin(graphYaw);
  const cosinePitch = Math.cos(graphPitch), sinePitch = Math.sin(graphPitch);
  const goldenAngle = Math.PI * (3 - Math.sqrt(5));
  for (const [key, group] of groups) {
    group.sort((left, right) => left.name.localeCompare(right.name) || left.id.localeCompare(right.id));
    const distance = key === "outer" ? null : Number(key);
    const radius = use3D ? (distance === null ? 178 : 33 + distance * 21)
      : (distance === null ? 244 : 46 + distance * 29);
    group.forEach((item, index) => {
      if (!use3D) {
        const angle = -Math.PI / 2 + (Math.PI * 2 * index) / group.length;
        positions.set(item.id, {x: centerX + radius * Math.cos(angle),
          y: centerY + radius * Math.sin(angle), distance, z: 0, scale: 1});
        return;
      }
      const vertical = 1 - 2 * ((index + 0.5) / group.length);
      const horizontal = Math.sqrt(Math.max(0, 1 - vertical * vertical));
      const angle = goldenAngle * index + (distance === null ? 2.7 : distance * 0.71);
      const originalX = radius * horizontal * Math.cos(angle);
      const originalY = radius * vertical;
      const originalZ = radius * horizontal * Math.sin(angle);
      const yawX = originalX * cosineYaw + originalZ * sineYaw;
      const yawZ = -originalX * sineYaw + originalZ * cosineYaw;
      const rotatedY = originalY * cosinePitch - yawZ * sinePitch;
      const rotatedZ = originalY * sinePitch + yawZ * cosinePitch;
      const perspective = 900 / (900 - rotatedZ);
      positions.set(item.id, {x: centerX + yawX * perspective,
        y: centerY + rotatedY * perspective, distance, z: rotatedZ, scale: perspective});
    });
  }
  return positions;
}
function renderYourProfile() {
  const conferenceId = new URLSearchParams(window.location.search).get("conference") || "";
  const own = profileTopicContext?.profile_session;
  const link = $("your-profile-link");
  link.href = `/start?conference=${encodeURIComponent(conferenceId)}`;
  link.textContent = own ? "Update my profile ↗" : "Add my profile ↗";
  $("your-profile-title").textContent = own ? "Your connections start with you" : "Find people relevant to you";
  $("your-profile-description").textContent = own
    ? (interestTopicIds.size ? `Matching attendees against ${interestTopicIds.size} of your interests. Select a person to see the reason and an opening line.`
      : "Your You node is ready. We haven’t found matching conference interests yet—add a few topics to see relevant people.")
    : "Add your LinkedIn or X profile to create your own node. You do not need to be in the attendee list.";
  const topics = $("your-profile-topics");
  topics.replaceChildren();
  for (const topic of conferenceTopics.filter(t => interestTopicIds.has(t.id)).slice(0, 8)) topics.append(node("span", topic.name, "person-topic-chip"));
  $("your-profile-interests").hidden = !own;
}
function graphWithTopics(base) {
  const own = profileTopicContext?.profile_session;
  const ownSelected = own && $("graph-my-profile").value === `self:${own.id}`;
  const nodes = base.nodes.slice(), edges = base.edges.slice();
  const showTopics = $("graph-show-topic-nodes").checked;
  const target = nodes.find(n => n.id === base.center_id);
  const topicMap = new Map();
  for (const topic of conferenceTopics) topicMap.set(topic.id, topic);
  for (const person of nodes) for (const topic of person.topics || []) topicMap.set(topic.id, topic);
  const ownTopics = conferenceTopics.filter(t => interestTopicIds.has(t.id));
  const wanted = Array.from(new Set([
    ...ownTopics.map(t => t.id), ...(target?.topics || []).map(t => t.id),
  ])).slice(0, 16);
  for (const id of showTopics ? wanted : []) {
    const topic = topicMap.get(id);
    if (!topic) continue;
    nodes.push({id: `topic:${id}`, name: topic.name, roles: ["topic"], kind: "topic", topics: [],
      distance: 1, connection_type: null});
    for (const person of base.nodes) {
      const attribution = (person.topics || []).find(t => t.id === id);
      if (attribution) edges.push({source: person.id, target: `topic:${id}`, category: "interest",
        evidence_ids: attribution.evidence_ids || []});
    }
  }
  let route = base.shortest_path;
  let source = base.comparison_source;
  if (ownSelected) {
    const ownId = `self:${own.id}`;
    nodes.push({id: ownId, name: "You", roles: ["self"], kind: "self", topics: ownTopics,
      distance: 2, connection_type: null});
    if (showTopics) {
      for (const topic of ownTopics.filter(t => wanted.includes(t.id))) {
        edges.push({source: ownId, target: `topic:${topic.id}`, category: "interest", evidence_ids: [],
          basis: "your_selected_interests"});
      }
    } else {
      for (const person of base.nodes) {
        const sharedTopics = (person.topics || []).filter(topic => interestTopicIds.has(topic.id));
        if (sharedTopics.length) edges.push({source: ownId, target: person.id, category: "interest",
          evidence_ids: Array.from(new Set(sharedTopics.flatMap(topic => topic.evidence_ids || []))),
          basis: "shared_interest", topic_names: sharedTopics.map(topic => topic.name)});
      }
    }
    const shared = ownTopics.find(t => (target?.topics || []).some(other => other.id === t.id));
    const persons = showTopics ? [ownId, `topic:${shared?.id}`, base.center_id] : [ownId, base.center_id];
    route = shared ? {status: "ok", persons, hops: showTopics ? 2 : 1, basis: "shared_interest",
      edges: edges.filter(e => e.category === "interest" && (showTopics
        ? e.target === `topic:${shared.id}` && [ownId, base.center_id].includes(e.source)
        : e.source === ownId && e.target === base.center_id))}
      : {status: "no_supported_path", persons: [], hops: null, edges: [], basis: "shared_interest"};
    source = ownId;
  }
  const pendingActions = followupItems.filter(item => item.status !== "done").slice(0, 20);
  if (pendingActions.length && privateActionSession) {
    const ownerId = ownSelected ? source : `self:${privateActionSession.id}`;
    if (!nodes.some(item => item.id === ownerId)) nodes.push({id: ownerId, name: "You", roles: ["self"], kind: "self", topics: []});
    for (const action of pendingActions) {
      if (!nodes.some(item => item.id === action.target)) nodes.push({id: action.target, name: action.target_name, roles: ["scheduled_speaker"], topics: []});
      const id = `action:${action.id}`;
      nodes.push({id, name: `Follow up · ${action.target_name} · ${action.channel}`, kind: "action", roles: ["action"], topics: []});
      edges.push({source: ownerId, target: id, category: "followup", evidence_ids: []}, {source: id, target: action.target, category: "action_for", evidence_ids: []});
    }
  }
  return {...base, nodes, edges, center_id: ownSelected ? source : base.center_id, target_id: base.center_id, shortest_path: route, comparison_source: source};
}
function routeEdgeKey(edge) {
  return JSON.stringify([...[edge.source, edge.target].sort(), edge.category]);
}
function renderShortestPath() {
  const area = $("graph-route-summary");
  area.replaceChildren();
  const visual = conferenceGraph ? graphWithTopics(conferenceGraph) : null;
  const route = visual?.shortest_path;
  if (!route || route.status === "needs_source") {
    area.append(node("p", "Choose your starting profile to find the shortest connection."));
    return;
  }
  if (route.status === "source_not_in_roster") {
    area.append(node("p", "Your starting profile is not in this conference roster. Choose a listed profile to compare."));
    return;
  }
  if (route.status !== "ok") {
    area.append(node("p", route.basis === "shared_interest"
      ? "Your profile node is ready. No shared topic is supported with this person yet; choose interests or another target."
      : "No cited path within six hops was found in this conference. This does not mean you have no connections in common."));
    return;
  }
  area.append(node("h3", route.hops === 0 ? "This is your starting profile" : `${route.basis === "shared_interest" ? "Shared-interest path" : "Shortest supported path"} · ${route.hops} ${route.hops === 1 ? "hop" : "hops"}`));
  const trail = node("div", undefined, "route-person-trail");
  const ids = Array.isArray(route.persons) ? route.persons : [];
  for (const [index, id] of ids.entries()) {
    if (index) trail.append(node("span", "→", "route-trail-arrow"));
    const visualNode = visual?.nodes.find(n => n.id === id);
    const name = visualNode?.name || conferenceRoster[id]?.name || names[id] || "Listed person";
    const chip = node("button", `${index === 0 ? (id.startsWith("self:") ? "" : id === $("graph-my-profile").value ? "You · " : "Start · ") : ""}${name}`);
    chip.type = "button";
    chip.disabled = visualNode?.kind === "topic" || visualNode?.kind === "self";
    chip.addEventListener("click", () => activateGraphNode(id));
    trail.append(chip);
  }
  area.append(trail, node("p", route.basis === "shared_interest"
    ? "Highlighted in gold. This matches your interests with their cited work; it is not a mutual-contact path."
    : "Highlighted in gold. These are cited public-work connections, not proof of friendship."));
  const sourceIds = Array.from(new Set((route.edges || []).flatMap(edge => edge.evidence_ids || [])))
    .filter(id => evidence[id] && safeHttpUrl(evidence[id].url));
  if (sourceIds.length) {
    const details = node("details");
    details.append(node("summary", "Check the path sources"));
    for (const [index, id] of sourceIds.entries()) details.append(sourceLink(evidence[id].url, `Source ${index + 1}`));
    area.append(details);
  }
}
function graphNodeClass(item, isCenter) {
  if (isCenter) return "graph-node graph-node-center";
  const roles = graphRoles(item.roles);
  if (roles.attendee && roles.speaker) return "graph-node graph-node-both";
  if (roles.attendee) return "graph-node graph-node-attendee";
  if (roles.speaker) return "graph-node graph-node-speaker";
  return "graph-node graph-node-other";
}
async function activateGraphNode(personId) {
  if (personId.startsWith("action:")) { $("saved-followups").scrollIntoView({block: "center"}); return; }
  targetChosenByUser = true;
  initialRecommendationChosen = true;
  const select = $("graph-focus");
  if (Array.from(select.options).some(option => option.value === personId)) select.value = personId;
  await loadConferenceGraph({focus: personId, query: $("graph-search").value.trim(), returnFocus: true});
  if (window.innerWidth <= 800 && conferenceGraph?.center_id === personId) {
    $("graph-person-detail").scrollIntoView({behavior: "instant", block: "start"});
  }
}
function graphSourceId() {
  const selectedStart = $("graph-my-profile").value;
  if (selectedStart && !selectedStart.startsWith("self:")) return selectedStart;
  return $("graph-public-comparison").checked ? $("try-source").value : "";
}
function graphSourceChanged() {
  targetChosenByUser = false;
  initialRecommendationChosen = false;
  if (conferenceGraph) {
    loadConferenceGraph({focus: graphSourceId() || conferenceGraph.center_id, query: $("graph-search").value.trim()});
  } else if (new URLSearchParams(window.location.search).has("conference")) {
    loadConferenceGraph({query: $("graph-search").value.trim()});
  }
}
function renderConferenceGraph(returnFocus = false, preserveDetail = false) {
  const svg = $("conference-graph");
  svg.replaceChildren();
  if (!conferenceGraph || !Array.isArray(conferenceGraph.nodes)) return;
  const use3D = $("graph-3d-toggle").checked;
  const centerX = 260, centerY = 260;
  svg.classList.toggle("graph-view-3d", use3D);
  svg.classList.toggle("graph-drag-active", Boolean(graphPointer?.dragging));
  svg.setAttribute("aria-label", use3D
    ? "Interactive 3D public people graph. Drag to rotate."
    : "Interactive 2D public people graph.");
  $("graph-rotate-hint").textContent = use3D
    ? "Drag to rotate."
    : "2D view · enable 3D to rotate.";
  const root = svgElement("g", {
    class: "graph-viewport",
    transform: `translate(${centerX * (1 - graphZoom)} ${centerY * (1 - graphZoom)}) scale(${graphZoom})`,
  });
  if (use3D) {
    for (let distance = 1; distance <= 6; distance += 1) {
      const radius = 33 + distance * 21;
      root.append(svgElement("ellipse", {cx: centerX, cy: centerY, rx: radius,
        ry: radius * 0.88, class: "graph-shell-guide"}));
    }
    root.append(svgElement("ellipse", {cx: centerX, cy: centerY, rx: 178, ry: 157,
      class: "graph-unreachable-ring"}));
    root.append(svgElement("ellipse", {cx: centerX, cy: centerY, rx: 178, ry: 52,
      class: "graph-sphere-latitude", transform: `rotate(${graphYaw * 18} ${centerX} ${centerY})`}));
    root.append(svgElement("text", {x: centerX, y: 76, class: "graph-unreachable-label",
      "text-anchor": "middle", "aria-hidden": "true"}, "No supported path in this view"));
  } else {
    for (let distance = 1; distance <= 6; distance += 1) {
      const radius = 46 + distance * 29;
      root.append(svgElement("circle", {cx: centerX, cy: centerY, r: radius, class: "graph-hop-ring"}));
      root.append(svgElement("text", {x: centerX, y: centerY - radius + 13,
        class: "graph-ring-label", "text-anchor": "middle", "aria-hidden": "true"}, String(distance)));
    }
    root.append(svgElement("circle", {cx: centerX, cy: centerY, r: 244, class: "graph-unreachable-ring"}));
    root.append(svgElement("text", {x: centerX, y: 25, class: "graph-unreachable-label",
      "text-anchor": "middle", "aria-hidden": "true"}, "No supported path in this view"));
  }

  const positions = graphPositions(conferenceGraph, use3D);
  const edges = (conferenceGraph.edges || []).map(edge => ({
    edge, from: positions.get(edge.source), to: positions.get(edge.target),
  })).filter(item => item.from && item.to && item.from !== item.to && edgeHasPublicCitation(item.edge));
  edges.sort((left, right) => (left.from.z + left.to.z) - (right.from.z + right.to.z));
  for (const {edge, from, to} of edges) {
    const depth = use3D ? Math.max(0.2, Math.min(0.72, 0.42 + ((from.z + to.z) / 2) / 700)) : 0.55;
    root.append(svgElement("line", {x1: from.x, y1: from.y, x2: to.x, y2: to.y,
      class: `graph-edge graph-edge-${edge.category}${(conferenceGraph.shortest_path?.edges || []).some(pathEdge => routeEdgeKey(pathEdge) === routeEdgeKey(edge)) ? " graph-edge-on-path" : ""}`, opacity: depth, "aria-hidden": "true"}));
  }
  const labelIds = new Set(conferenceGraph.nodes.filter(item => item.id !== conferenceGraph.center_id
    && item.distance !== null).slice().sort((left, right) => left.distance - right.distance
    || left.name.localeCompare(right.name)).slice(0, 13).map(item => item.id));
  const renderNodes = conferenceGraph.nodes.slice().sort((left, right) => {
    if (left.id === conferenceGraph.center_id) return 1;
    if (right.id === conferenceGraph.center_id) return -1;
    return (positions.get(left.id)?.z || 0) - (positions.get(right.id)?.z || 0);
  });
  for (const item of renderNodes) {
    const point = positions.get(item.id);
    if (!point || typeof item.name !== "string" || !Array.isArray(item.roles)) continue;
    const isCenter = item.id === conferenceGraph.center_id;
    const roles = graphRoleLabel(item.roles);
    const distanceLabel = graphDistanceLabel(point.distance, isCenter);
    const group = svgElement("g", {
      class: graphNodeClass(item, isCenter),
      role: "button",
      tabindex: "0",
      "aria-label": `${item.name}, ${roles}, ${distanceLabel}. Activate to focus this profile.`,
      "aria-pressed": isCenter ? "true" : "false",
      "data-node-id": item.id,
    });
    group.append(svgElement("title", {}, `${item.name} · ${roles} · ${distanceLabel}`));
    const nodeScale = use3D ? point.scale : 1;
    group.append(svgElement("circle", {cx: point.x, cy: point.y,
      r: Math.max(6, (isCenter ? 15 : 10) * nodeScale), opacity: use3D ? 0.66 + nodeScale * 0.27 : 1}));
    if (isCenter || nodeScale > 0.85) group.append(svgElement("text", {
      x: point.x, y: point.y + 3, "text-anchor": "middle", class: "graph-node-initials",
      "aria-hidden": "true",
    }, item.name.trim().split(/\s+/).slice(0, 2).map(part => part[0]).join("")));
    let anchor = "middle", labelX = point.x, labelY = point.y + (isCenter ? 33 : 25);
    if (!isCenter) {
      const dx = point.x - centerX;
      anchor = dx > 12 ? "start" : (dx < -12 ? "end" : "middle");
      labelX += dx > 12 ? 14 : (dx < -12 ? -14 : 0);
      labelY = point.y + 4;
    }
    const quietLabel = !isCenter && !labelIds.has(item.id);
    group.append(svgElement("text", {x: labelX, y: labelY,
      class: quietLabel ? "graph-node-label graph-label-quiet" : "graph-node-label",
      "text-anchor": anchor}, isCenter ? item.name : textShort(item.name)));
    if (isCenter) {
      const categoryLabels = {mirror: "Mirror", missing_piece: "Missing piece",
        unexpected_connection: "Unexpected connection"};
      if (categoryLabels[item.connection_type]) {
        group.append(svgElement("text", {x: point.x, y: labelY + 17,
          class: "graph-category-label", "text-anchor": "middle"}, categoryLabels[item.connection_type]));
      }
    }
    group.addEventListener("click", () => activateGraphNode(item.id));
    group.addEventListener("keydown", event => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        activateGraphNode(item.id);
      }
    });
    root.append(group);
  }
  svg.append(root);
  renderShortestPath();
  if (window.WarmOpenGraphKit) window.WarmOpenGraphKit.update({
    graph: graphWithTopics(conferenceGraph),
    edges: graphWithTopics(conferenceGraph).edges.filter(edge => ["interest", "followup", "action_for"].includes(edge.category) || edgeHasPublicCitation(edge)),
    dimension: use3D ? "3d" : "2d",
    layout: $("graph-layout-mode").value,
    onSelect: activateGraphNode,
  });
  if (!preserveDetail) renderGraphDetail(conferenceGraph.center_id);
  if (returnFocus) {
    const selected = Array.from(svg.querySelectorAll("[data-node-id]"))
      .find(element => element.getAttribute("data-node-id") === conferenceGraph.center_id);
    selected?.focus();
  }
}
function setGraphControlsLoading(loading) {
  for (const id of ["graph-search", "graph-search-button", "graph-focus"]) $(id).disabled = loading;
}
function setupGraphRotation() {
  const svg = $("conference-graph");
  svg.addEventListener("pointerdown", event => {
    if (!$("graph-3d-toggle").checked || event.button !== 0) return;
    graphPointer = {pointerId: event.pointerId, startX: event.clientX, startY: event.clientY,
      lastX: event.clientX, lastY: event.clientY, dragging: false};
    try { svg.setPointerCapture(event.pointerId); } catch (_) { /* Pointer capture is optional. */ }
  });
  svg.addEventListener("pointermove", event => {
    if (!graphPointer || event.pointerId !== graphPointer.pointerId) return;
    const dx = event.clientX - graphPointer.lastX;
    const dy = event.clientY - graphPointer.lastY;
    if (!graphPointer.dragging
        && Math.hypot(event.clientX - graphPointer.startX, event.clientY - graphPointer.startY) > 4) {
      graphPointer.dragging = true;
    }
    if (!graphPointer.dragging) return;
    const bounds = svg.getBoundingClientRect();
    graphYaw += dx * (Math.PI * 2 / Math.max(1, bounds.width));
    graphPitch = Math.max(-1.35, Math.min(1.35,
      graphPitch + dy * (Math.PI / Math.max(1, bounds.height))));
    graphPointer.lastX = event.clientX;
    graphPointer.lastY = event.clientY;
    if (event.cancelable) event.preventDefault();
    renderConferenceGraph(false, true);
  });
  const finishPointer = event => {
    if (!graphPointer || event.pointerId !== graphPointer.pointerId) return;
    const pointerId = graphPointer.pointerId;
    const didDrag = graphPointer.dragging;
    graphPointer = null;
    if (didDrag) {
      suppressGraphClick = true;
      window.setTimeout(() => { suppressGraphClick = false; }, 0);
    }
    try { if (svg.hasPointerCapture(pointerId)) svg.releasePointerCapture(pointerId); }
    catch (_) { /* Capture may already have been released by the browser. */ }
    svg.classList.remove("graph-drag-active");
  };
  svg.addEventListener("pointerup", finishPointer);
  svg.addEventListener("pointercancel", finishPointer);
  svg.addEventListener("click", event => {
    if (!suppressGraphClick) return;
    suppressGraphClick = false;
    event.preventDefault();
    event.stopImmediatePropagation();
  }, true);
}
async function loadConferenceGraph({focus, query = "", returnFocus = false} = {}) {
  const conferenceId = new URLSearchParams(window.location.search).get("conference");
  if (!conferenceId) return;
  const token = ++graphRequestToken;
  setGraphControlsLoading(true);
  $("graph-status").textContent = "Loading cited public graph connections…";
  try {
    const body = {limit: GRAPH_LIMIT};
    if (focus) body.focus = focus;
    if (query) body.query = query;
    const source = graphSourceId();
    if (source) body.source = source;
    body.interest_topic_ids = Array.from(interestTopicIds);
    body.seeking_topic_ids = Array.from(seekingTopicIds);
    const response = await fetch(`/api/conferences/${encodeURIComponent(conferenceId)}/graph`, {
      method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body),
    });
    if (!response.ok) throw new Error("Graph unavailable");
    const data = await response.json();
    if (token !== graphRequestToken) return;
    if (!Array.isArray(data.nodes) || !Array.isArray(data.edges)
        || typeof data.center_id !== "string") throw new Error("Graph unavailable");
    data.nodes = data.nodes.filter(item => item && typeof item.id === "string"
      && typeof item.name === "string" && Array.isArray(item.roles)
      && (item.distance === null || (Number.isInteger(item.distance) && item.distance >= 0 && item.distance <= 6)));
    data.edges = data.edges.filter(edge => edge && typeof edge.source === "string"
      && typeof edge.target === "string" && GRAPH_CATEGORIES.has(edge.category)
      && Array.isArray(edge.evidence_ids));
    conferenceGraph = data;
    Object.assign(evidence, data.evidence || {});
    Object.assign(names, data.people || {});
    if (!defaultGraphFocus) defaultGraphFocus = data.center_id;
    if (Array.from($("graph-focus").options).some(option => option.value === data.center_id)) {
      $("graph-focus").value = data.center_id;
    }
    renderConferenceGraph(returnFocus);
    renderYourProfile();
    const shown = data.nodes.length;
    const total = Number.isInteger(data.total_count) ? data.total_count : shown;
    const rosterCount = Number.isInteger(data.roster_count) ? data.roster_count : conferenceRosterCount();
    let message = `${shown} people on the map · ${rosterCount} in this conference`;
    if (data.truncated) message += " · Search to find someone else";
    $("graph-status").textContent = message;
    loadPeopleMatches();
  } catch (_) {
    if (token === graphRequestToken) {
      $("conference-graph").replaceChildren();
      $("graph-status").textContent = "The cited conference graph is temporarily unavailable.";
    }
  } finally {
    if (token === graphRequestToken) setGraphControlsLoading(false);
  }
}
async function loadPeopleMatches() {
  const conferenceId = new URLSearchParams(window.location.search).get("conference");
  if (!conferenceId) return;
  const source = graphSourceId();
  const context = matchContext();
  const body = {interest_topic_ids: context.interest_topic_ids, seeking_topic_ids: context.seeking_topic_ids};
  if (source) body.source = source;
  const key = JSON.stringify([conferenceId, body]);
  if (key === peopleMatchesKey) return;
  peopleMatchesKey = key;
  const request = ++peopleMatchesRequest;
  $("people-matches-status").textContent = "Finding people across the conference…";
  try {
    const response = await fetch(`/api/conferences/${encodeURIComponent(conferenceId)}/matches`, {
      method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body),
    });
    if (!response.ok) throw new Error("Matches unavailable");
    const data = await response.json();
    if (request !== peopleMatchesRequest) return;
    Object.assign(evidence, data.evidence || {});
    const items = Array.isArray(data.items) ? data.items.filter(person => ["mirror", "missing_piece", "unexpected_connection"].includes(person.category)) : [];
    peopleMatchScores.clear();
    for (const person of items) {
      const topicCount = (person.topics || []).length;
      const citationCount = new Set(person.evidence_ids || []).size;
      person.starting_score = Math.min(90, (DEFAULT_CATEGORY_SCORES[person.category] || 20)
        + Math.min(40, topicCount * 10) + Math.min(10, citationCount * 2));
      peopleMatchScores.set(`${person.id}:${person.category}`, person.starting_score);
    }
    items.sort((a, b) => b.starting_score - a.starting_score || a.name.localeCompare(b.name));
    const hasContext = Boolean(source || interestTopicIds.size || seekingTopicIds.size);
    const groups = [["mirror", "mirror"], ["missing_piece", "missing"], ["unexpected_connection", "unexpected"]];
    for (const [category, prefix] of groups) {
      const list = $(`${prefix}-people`), matching = items.filter(person => person.category === category);
      list.replaceChildren();
      $(`${prefix}-count`).textContent = hasContext ? String(matching.length) : "—";
      if (!matching.length) list.append(node("p", hasContext ? "No supported matches in this category for the current interests and starting profile." : "Not assessed yet. Choose interests or a starting profile to assess matches.", "people-match-empty"));
      for (const person of matching) {
        const card = node("article", undefined, "people-match-card");
        const button = node("button", person.name, "people-match-person");
        button.type = "button";
        button.onclick = async () => {
          $("graph-search").value = "";
          await activateGraphNode(person.id);
          $("graph-person-detail").scrollIntoView({behavior: "instant", block: "start"});
        };
        const pair = (person.topics || [])[0];
        const why = pair?.source?.name && pair?.target?.name
          ? (pair.relation === "related" ? `${pair.source.name} connects to their work on ${pair.target.name}.`
            : `Their cited work on ${pair.target.name} matches ${person.category === "missing_piece" ? "what you need" : "your interests"}.`)
          : person.reason || "Based on cited professional work.";
        const heading = node("div", undefined, "people-match-card-heading");
        const score = node("span", `~${person.starting_score}/100`, "person-match-score");
        score.title = "Uncalibrated starting estimate from matched topics and cited evidence, not a probability.";
        heading.append(button, score);
        card.append(heading, node("p", "Uncalibrated starting fit", "person-match-score-label"), node("p", why, "people-match-reason"));
        const chips = node("div", undefined, "person-topics");
        for (const topic of (person.topics || []).slice(0, 3)) chips.append(node("span", topic.name || topic.target?.name || topic.id || "Related topic", "person-topic-chip"));
        card.append(chips);
        const id = (person.evidence_ids || []).find(id => evidence[id] && safeHttpUrl(evidence[id].url));
        if (id) card.append(sourceLink(evidence[id].url, "See the public source ↗"));
        list.append(card);
      }
    }
    if (!initialRecommendationChosen && !targetChosenByUser && items.length
        && (source || (profileTopicContext?.profile_session && $("graph-my-profile").value.startsWith("self:")))) {
      initialRecommendationChosen = true;
      const recommended = items.find(item => item.category === "missing_piece") || items.find(item => item.category === "mirror") || items[0];
      if (conferenceGraph?.center_id !== recommended.id) {
        $("graph-focus").value = recommended.id;
        loadConferenceGraph({focus: recommended.id, query: ""});
      }
    }
    if (conferenceGraph && conversationResults.has(conversationKey(conferenceGraph.center_id))) renderGraphDetail(conferenceGraph.center_id);
    const unknown = Number.isInteger(data.unclassified_count) ? data.unclassified_count : 0;
    $("people-matches-title").textContent = source ? `People relevant to ${conferenceRoster[source]?.name || names[source] || "the selected profile"}` : "People relevant to you.";
    $("people-matches-status").textContent = items.length
      ? `${items.length} suggestions across the conference${unknown ? ` · ${unknown} people need more context` : ""}. Topic-based suggestions are starting points, not friendship predictions.`
      : "Choose interests or a starting profile to find mirrors, complements, and adjacent expertise.";
  } catch (_) {
    if (request !== peopleMatchesRequest) return;
    peopleMatchesKey = "";
    $("people-matches-status").textContent = "People suggestions are temporarily unavailable. You can still explore the map.";
  }
}
function conferenceRosterCount() {
  return Object.keys(conferenceRoster).length;
}
function populateGraphFocus() {
  const select = $("graph-focus"), previous = select.value;
  const entries = Object.values(conferenceRoster)
    .sort((left, right) => (left.name || "").localeCompare(right.name || "") || left.id.localeCompare(right.id));
  const placeholder = new Option("Choose a public profile", "");
  select.replaceChildren(placeholder, ...entries.map(person => new Option(person.name || "Unnamed public profile", person.id)));
  if (entries.some(person => person.id === previous)) select.value = previous;
  const mine = $("graph-my-profile"), selectedMine = mine.value;
  mine.replaceChildren(new Option("Choose your name from the public roster…", ""),
    ...entries.map(person => new Option(person.name || "Unnamed public profile", person.id)));
  const own = profileTopicContext?.profile_session;
  if (own) {
    const selfOption = new Option("You · Your profile", `self:${own.id}`);
    mine.insertBefore(selfOption, mine.options[1] || null);
    mine.value = selectedMine || selfOption.value;
    $("graph-starting-note").textContent = "Your profile node is ready. Interest links are distinct from connections through people.";
  } else if (entries.some(person => person.id === selectedMine)) mine.value = selectedMine;
}
function readProfileTopicContext(conferenceId) {
  try {
    const saved = JSON.parse(sessionStorage.getItem(PROFILE_CONTEXT_KEY) || "null");
    if (!saved || saved.conference_id !== conferenceId) return null;
    const topics = Array.isArray(saved.topics) ? saved.topics.filter(item => item
      && typeof item.id === "string" && typeof item.name === "string") : [];
    return {
      interest_topic_ids: Array.isArray(saved.interest_topic_ids)
        ? saved.interest_topic_ids.filter(value => typeof value === "string") : [],
      seeking_topic_ids: Array.isArray(saved.seeking_topic_ids)
        ? saved.seeking_topic_ids.filter(value => typeof value === "string") : [],
      topics,
      profile_session: saved.profile_session && typeof saved.profile_session.id === "string" ? saved.profile_session : null,
      profile_sources: Array.isArray(saved.profile_sources) ? saved.profile_sources : [],
    };
  } catch (_) { return null; }
}
function persistTopicSelections(conferenceId) {
  profileTopicContext = {
    profile_session: profileTopicContext?.profile_session || null,
    profile_sources: profileTopicContext?.profile_sources || [],
    conference_id: conferenceId,
    interest_topic_ids: Array.from(interestTopicIds),
    seeking_topic_ids: Array.from(seekingTopicIds),
    topics: conferenceTopics.filter(item => interestTopicIds.has(item.id)
      || seekingTopicIds.has(item.id)).map(item => ({id: item.id, name: item.name})),
  };
  try { sessionStorage.setItem(PROFILE_CONTEXT_KEY, JSON.stringify(profileTopicContext)); }
  catch (_) { /* Continue with in-memory choices if session storage is unavailable. */ }
}
function renderTopicChips(container, topicIds, selected, groupName) {
  container.replaceChildren();
  if (!topicIds.length) {
    container.append(node("p", "No cited topics are available yet.", "topic-empty"));
    return;
  }
  topicIds.forEach((topic, index) => {
    const label = node("label", undefined, "topic-chip");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.id = `${groupName}-topic-${index}`;
    input.value = topic.id;
    input.checked = selected.has(topic.id);
    input.addEventListener("change", () => {
      if (input.checked) selected.add(topic.id);
      else selected.delete(topic.id);
      const conferenceId = new URLSearchParams(window.location.search).get("conference");
      if (conferenceId) {
        persistTopicSelections(conferenceId);
        invalidateMatchViews();
        loadConferenceGraph({focus: conferenceGraph?.center_id, query: $("graph-search").value.trim()});
      }
    });
    label.append(input, node("span", topic.name));
    container.append(label);
  });
}
function renderTopicPickers(items, conferenceId) {
  const byId = new Map();
  for (const item of items || []) {
    if (item && typeof item.id === "string" && typeof item.name === "string") byId.set(item.id, item);
  }
  if (!byId.size && profileTopicContext) {
    conferenceTopics = [];
    interestTopicIds = new Set();
    seekingTopicIds = new Set();
    renderTopicChips($("interest-topics"), conferenceTopics, interestTopicIds, "interest");
    renderTopicChips($("seeking-topics"), conferenceTopics, seekingTopicIds, "seeking");
    return;
  }
  conferenceTopics = Array.from(byId.values()).sort((left, right) => left.name.localeCompare(right.name));
  interestTopicIds = new Set(profileTopicContext?.interest_topic_ids || []);
  seekingTopicIds = new Set(profileTopicContext?.seeking_topic_ids || []);
  interestTopicIds = new Set(conferenceTopics.filter(item => interestTopicIds.has(item.id)).map(item => item.id));
  seekingTopicIds = new Set(conferenceTopics.filter(item => seekingTopicIds.has(item.id)).map(item => item.id));
  renderTopicChips($("interest-topics"), conferenceTopics, interestTopicIds, "interest");
  renderTopicChips($("seeking-topics"), conferenceTopics, seekingTopicIds, "seeking");
  if (profileTopicContext) persistTopicSelections(conferenceId);
}
function renderGraphRoster(attendees, speakers) {
  conferenceRoster = {};
  for (const person of attendees) {
    conferenceRoster[person.id] = {...person, roles: ["confirmed_attendee"]};
  }
  for (const person of speakers) {
    const existing = conferenceRoster[person.id] || {...person, roles: []};
    existing.roles = Array.from(new Set([...(existing.roles || []), "scheduled_speaker"]));
    existing.evidence_ids = Array.from(new Set([...(existing.evidence_ids || []), ...(person.evidence_ids || [])]));
    existing.talks = person.talks || existing.talks || [];
    conferenceRoster[person.id] = existing;
  }
  populateGraphFocus();
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
    let topicItems = [];
    try {
      const topicResponse = await fetch(`/api/conferences/${encodeURIComponent(conferenceId)}/topics`).then(checkedJson);
      topicItems = topicResponse.items || [];
      Object.assign(evidence, topicResponse.evidence || {});
    } catch (_) { /* The graph and roster remain usable when topic suggestions are unavailable. */ }
    const conference = (directory.items || []).find(item => item.id === conferenceId);
    $("explore-conference-title").textContent = conference?.name || "Conference directory";
    $("explore-conference-dates").textContent = conference?.starts && conference?.ends
      ? `${conference.starts} – ${conference.ends}` : "Browse the public people listed for this conference.";
    profileTopicContext = readProfileTopicContext(conferenceId);
    renderGraphRoster(peopleResponse.confirmed_attendees || [], peopleResponse.scheduled_speakers || []);
    renderDirectoryRows($("explore-attendees"), peopleResponse.confirmed_attendees || [], "attendee");
    renderDirectoryRows($("explore-speakers"), peopleResponse.scheduled_speakers || [], "speaker");
    profileTopicContext = readProfileTopicContext(conferenceId);
    renderTopicPickers(topicItems, conferenceId);
    await loadConferenceGraph();
    await loadFollowups();
  } catch (_) {
    $("explore-conference-title").textContent = "Conference directory unavailable";
    $("explore-conference-dates").textContent = "Public profile exploration is still available below.";
    $("explore-attendees").replaceChildren(node("p", "Attendee information could not be loaded.", "quiet-copy"));
    $("explore-speakers").replaceChildren(node("p", "Speaker information could not be loaded.", "quiet-copy"));
    $("graph-status").textContent = "Conference people information could not be loaded.";
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
  selectionChanged(); graphSourceChanged(); action("paths");
};
function selectionChanged() {
  $("try-path-results").replaceChildren();
  $("try-opener-results").replaceChildren();
  $("try-status").textContent = "Choose two distinct public profiles, then search.";
  controls();
}
$("try-source").onchange = () => {
  $("graph-my-profile").value = $("try-source").value;
  $("graph-public-comparison").checked = Boolean($("try-source").value);
  selectionChanged();
  targetChosenByUser = false;
  invalidateMatchViews();
  graphSourceChanged();
};
$("try-target").onchange = () => {
  selectionChanged();
  if (conferenceRoster[$("try-target").value]) activateGraphNode($("try-target").value);
};
$("try-source-filter").oninput = () => {
  const previous = $("try-source").value;
  populateSelect("try-source", "try-source-filter");
  selectionChanged();
  if (previous !== $("try-source").value) graphSourceChanged();
};
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
$("graph-search-button").onclick = () => {
  targetChosenByUser = true;
  initialRecommendationChosen = true;
  loadConferenceGraph({focus: $("graph-focus").value || conferenceGraph?.center_id,
    query: $("graph-search").value.trim()});
};
$("graph-search").onkeydown = event => {
  if (event.key === "Enter") {
    event.preventDefault();
    $("graph-search-button").click();
  }
};
$("graph-focus").onchange = () => {
  targetChosenByUser = true;
  initialRecommendationChosen = true;
  loadConferenceGraph({focus: $("graph-focus").value, query: $("graph-search").value.trim()});
};
$("graph-public-comparison").onchange = () => {
  $("graph-my-profile").value = "";
  invalidateMatchViews();
  graphSourceChanged();
};
$("graph-zoom-in").onclick = () => { graphZoom = Math.min(1.6, graphZoom + 0.15); window.WarmOpenGraphKit?.zoom(1.2); renderConferenceGraph(); };
$("graph-zoom-out").onclick = () => { graphZoom = Math.max(0.7, graphZoom - 0.15); window.WarmOpenGraphKit?.zoom(1 / 1.2); renderConferenceGraph(); };
$("graph-zoom-reset").onclick = () => {
  graphZoom = 1;
  graphYaw = -0.35;
  graphPitch = 0.28;
  $("graph-search").value = "";
  if (defaultGraphFocus) $("graph-focus").value = defaultGraphFocus;
  loadConferenceGraph({focus: defaultGraphFocus || undefined, query: ""});
};
$("graph-3d-toggle").onchange = () => renderConferenceGraph();
$("your-profile-interests").onclick = () => {
  $("graph-topic-picker").open = true;
  $("graph-topic-picker").scrollIntoView({behavior: "instant", block: "center"});
  $("graph-topic-picker").querySelector("summary").focus();
};
$("graph-my-profile").onchange = () => {
  $("try-source-filter").value = "";
  populateSelect("try-source", "try-source-filter");
  const ownSelected = $("graph-my-profile").value.startsWith("self:");
  $("try-source").value = ownSelected ? "" : $("graph-my-profile").value;
  $("graph-public-comparison").checked = !ownSelected && Boolean($("graph-my-profile").value);
  invalidateMatchViews();
  graphSourceChanged();
};
$("graph-layout-mode").onchange = () => renderConferenceGraph();
$("graph-show-topic-nodes").onchange = () => renderConferenceGraph();
$("graph-fit-view").onclick = () => window.WarmOpenGraphKit?.fit();
window.addEventListener("graph-context-node", event => {
  const data = event.detail;
  if (!data || !conferenceGraph) return;
  const area = $("graph-person-detail");
  area.replaceChildren();
  area.append(node("p", data.kind === "self" ? "YOUR PRIVATE SESSION PROFILE" : "PROFESSIONAL TOPIC", "graph-detail-kicker"),
    node("h2", data.kind === "self" ? "You" : data.name));
  if (data.kind === "self") {
    area.append(node("p", "Your public-profile interests and the topics you choose connect you to this conference. These links do not imply that you know someone.", "quiet-copy"));
    const topics = node("div", undefined, "person-topics");
    for (const topic of data.topics || []) topics.append(node("span", topic.name, "person-topic-chip"));
    area.append(topics);
  } else {
    area.append(node("p", "People with cited work on this topic", "quiet-copy"));
    for (const person of conferenceGraph.nodes.filter(person => (person.topics || []).some(t => `topic:${t.id}` === data.personId))) {
      const button = node("button", person.name, "topic-person-link");
      button.type = "button";
      button.onclick = () => activateGraphNode(person.id);
      area.append(button);
    }
  }
  const back = node("button", "Back to selected person", "graph-action-button");
  back.type = "button";
  back.onclick = () => renderGraphDetail(conferenceGraph.center_id);
  area.append(back);
});
window.addEventListener("falkordb-canvas-ready", () => { if (conferenceGraph) renderConferenceGraph(); });
setupGraphRotation();
init();
loadConferenceContext();

$("save-followup").onclick = () => saveFollowup();
