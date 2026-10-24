"use strict";
const $ = id => document.getElementById(id);
const STORAGE_KEY = "warmopen_profile_links";
const PROFILE_CONTEXT_KEY = "warmopen_profile_context_v1";
const params = new URLSearchParams(window.location.search);
const conferenceId = params.get("conference") || "";
document.title = `${PRODUCT_NAME} · Conference`;
$("start-brand").textContent = PRODUCT_NAME;
let storageAvailable = true;
let enrichmentFinished = false;
let enrichmentInFlight = false;
let profileRequestToken = 0;

function goToExplore() {
  if (!conferenceId) window.location.assign("/try");
  else window.location.assign(`/explore?conference=${encodeURIComponent(conferenceId)}`);
}
function rejectReserved(handle) {
  return new Set(["about", "account", "admin", "api", "compose", "explore", "hashtag",
    "home", "intent", "i", "jobs", "login", "messages", "notifications", "privacy",
    "search", "settings", "share", "signup", "tos"]).has(handle.toLowerCase());
}
function validateLinkedIn(value) {
  if (!value.trim()) return {value: "", error: ""};
  if (/\s/.test(value)) return {value: "", error: "Remove spaces from the LinkedIn profile URL."};
  try {
    const url = new URL(value.trim());
    const match = url.pathname.match(/^\/in\/([A-Za-z0-9-]{3,100})\/?$/);
    if (url.protocol !== "https:" || !["linkedin.com", "www.linkedin.com"].includes(url.hostname)
        || url.username || url.password || url.port || url.search || url.hash
        || /[?#]/.test(value) || !match) {
      return {value: "", error: "Use a LinkedIn profile URL in the form linkedin.com/in/your-name."};
    }
    return {value: `https://linkedin.com/in/${match[1]}`, error: ""};
  } catch (_) {
    return {value: "", error: "Enter a valid HTTPS LinkedIn profile URL."};
  }
}
function validateX(value) {
  if (!value.trim()) return {value: "", error: ""};
  if (/\s/.test(value)) return {value: "", error: "Remove spaces from the X or Twitter profile URL."};
  try {
    const url = new URL(value.trim());
    const match = url.pathname.match(/^\/([A-Za-z0-9_]{1,15})\/?$/);
    const hosts = ["x.com", "www.x.com", "twitter.com", "www.twitter.com"];
    if (url.protocol !== "https:" || !hosts.includes(url.hostname) || url.username || url.password
        || url.port || url.search || url.hash || /[?#]/.test(value) || !match
        || rejectReserved(match?.[1] || "")) {
      return {value: "", error: "Use a single public profile path, such as x.com/yourname."};
    }
    return {value: `https://x.com/${match[1]}`, error: ""};
  } catch (_) {
    return {value: "", error: "Enter a valid HTTPS X or Twitter profile URL."};
  }
}
function readSaved() {
  try {
    const saved = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || "{}");
    $("profile-linkedin").value = typeof saved.linkedin === "string" ? saved.linkedin : "";
    $("profile-x").value = typeof saved.x === "string" ? saved.x : "";
  } catch (_) {
    storageAvailable = false;
    $("profile-status").textContent = "Session storage is unavailable. You can still explore without saving profile links.";
  }
}
function saveProfileLinks(linkedin, x) {
  if (!storageAvailable) return;
  try {
    if (linkedin || x) sessionStorage.setItem(STORAGE_KEY, JSON.stringify({linkedin, x}));
    else sessionStorage.removeItem(STORAGE_KEY);
  } catch (_) { storageAvailable = false; }
}
function showEnrichment(data) {
  const result = $("profile-enrichment-result");
  result.replaceChildren();
  result.hidden = false;
  const topics = Array.isArray(data.topics) ? data.topics.filter(topic => topic
    && typeof topic.id === "string" && typeof topic.name === "string") : [];
  const heading = ["complete", "partial"].includes(data.status) && topics.length
    ? "Known conference topics found"
    : (["provider_unconfigured", "provider_error", "pending", "topic_lookup_failed"].includes(data.status)
      ? "Profile research is not complete"
      : (data.status === "no_profile_data" ? "No public profile information was available"
        : (data.status === "no_conference_topics" ? "No cited conference topics are available"
          : "No conference topics were found")));
  result.append(document.createElement("h3"));
  result.lastElementChild.textContent = heading;
  if (topics.length) {
    const list = document.createElement("ul");
    for (const topic of topics) {
      const item = document.createElement("li");
      item.textContent = topic.name;
      list.append(item);
    }
    result.append(list);
  } else {
    const message = document.createElement("p");
    message.textContent = ["provider_unconfigured", "provider_error", "pending", "topic_lookup_failed"].includes(data.status)
      ? "Profile research could not provide results right now. You can continue without it."
      : "You can continue and choose topics manually in the conference graph.";
    result.append(message);
  }
  const sources = Array.isArray(data.sources) ? data.sources.slice(0, 4) : [];
  if (sources.length) {
    const sourceList = document.createElement("p");
    sourceList.className = "profile-enrichment-sources";
    sourceList.append(document.createTextNode("Research sources: "));
    let shownSources = 0;
    for (const source of sources) {
      let url;
      try {
        const parsed = new URL(source.url);
        if (!["https:", "http:"].includes(parsed.protocol)) continue;
        url = parsed.href;
      } catch (_) { continue; }
      if (shownSources) sourceList.append(document.createTextNode(" · "));
      const link = document.createElement("a");
      link.href = url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = source.platform === "linkedin" ? "LinkedIn source" : "X source";
      sourceList.append(link);
      shownSources += 1;
    }
    result.append(sourceList);
  }
}
function saveTopicContext(data) {
  const topics = Array.isArray(data.topics) ? data.topics.filter(topic => topic
    && typeof topic.id === "string" && typeof topic.name === "string") : [];
  const topicIds = Array.isArray(data.topic_ids)
    ? data.topic_ids.filter(id => typeof id === "string" && topics.some(topic => topic.id === id)) : [];
  const context = {
    conference_id: conferenceId,
    interest_topic_ids: Array.from(new Set(topicIds)),
    seeking_topic_ids: [],
    topics,
    profile_session: data.profile_session || null,
    profile_sources: Array.isArray(data.sources) ? data.sources : [],
  };
  try {
    sessionStorage.setItem(PROFILE_CONTEXT_KEY, JSON.stringify(context));
    return context.interest_topic_ids.length;
  } catch (_) {
    return -1;
  }
}
async function loadConference() {
  if (!conferenceId) {
    $("start-title").textContent = "Choose a conference first.";
    $("start-dates").textContent = "Return to the conference directory to select an event.";
    $("profile-form").hidden = true;
    $("skip-button").href = "/try";
    return;
  }
  $("skip-button").href = `/explore?conference=${encodeURIComponent(conferenceId)}`;
  try {
    const response = await fetch("/api/conferences");
    if (!response.ok) throw new Error("Conference request failed.");
    const data = await response.json();
    const event = (data.items || []).find(item => item.id === conferenceId);
    if (event) {
      $("start-title").textContent = event.name;
      $("start-dates").textContent = event.starts && event.ends
        ? `${event.starts} – ${event.ends}` : "Conference dates are not listed.";
    } else {
      $("start-title").textContent = "Conference listing unavailable.";
      $("start-dates").textContent = "You can still explore the public directory.";
    }
  } catch (_) {
    $("start-title").textContent = "Conference listing unavailable.";
    $("start-dates").textContent = "You can still explore the public directory.";
  }
}
function validatedInputs() {
  const linkedin = validateLinkedIn($("profile-linkedin").value);
  const x = validateX($("profile-x").value);
  $("linkedin-error").textContent = linkedin.error;
  $("x-error").textContent = x.error;
  $("profile-linkedin").setAttribute("aria-invalid", String(Boolean(linkedin.error)));
  $("profile-x").setAttribute("aria-invalid", String(Boolean(x.error)));
  if (linkedin.error || x.error) {
    (linkedin.error ? $("profile-linkedin") : $("profile-x")).focus();
    return null;
  }
  return {linkedin: linkedin.value, x: x.value};
}
async function enrichProfile(links) {
  if (!links.linkedin && !links.x) {
    $("profile-status").textContent = "Enter at least one of your public profile URLs to request research, or skip profile research.";
    return;
  }
  const requestToken = ++profileRequestToken;
  enrichmentInFlight = true;
  $("continue-button").disabled = true;
  $("profile-status").textContent = "Looking for public professional topics from your profile links…";
  const body = {conference_id: conferenceId, consent: true};
  if (links.linkedin) body.linkedin = links.linkedin;
  if (links.x) body.x = links.x;
  try {
    const response = await fetch("/api/profile/enrich", {
      method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body),
    });
    if (!response.ok) throw new Error("Profile research unavailable");
    const data = await response.json();
    if (requestToken !== profileRequestToken) return;
    if (!["complete", "partial", "pending", "provider_unconfigured", "no_conference_topics",
      "no_profile_data", "no_profiles", "provider_error", "topic_lookup_failed",
      "invalid_profile_url", "consent_required", "profile_storage_failed"].includes(data.status)) {
      throw new Error("Profile research unavailable");
    }
    const topicsSaved = saveTopicContext(data);
    showEnrichment(data);
    enrichmentFinished = true;
    $("continue-button").textContent = "See people at this conference";
    if (["complete", "partial"].includes(data.status) && topicsSaved > 0) {
      $("profile-status").textContent = data.status === "partial"
        ? "Some profile sources were unavailable; matched topic interests are ready for this session."
        : "Your topic interests are ready for this conference session.";
    } else if (["complete", "partial"].includes(data.status)
        && (data.topic_ids || []).length && topicsSaved < 0) {
      $("profile-status").textContent = "Topics were found, but this browser could not save them for the next page.";
    } else if (["provider_unconfigured", "provider_error", "pending", "topic_lookup_failed"].includes(data.status)) {
      $("profile-status").textContent = "Profile research could not be completed yet. You can continue without it.";
    } else {
      $("profile-status").textContent = "No conference topic matches were found. You can choose topics manually.";
    }
  } catch (_) {
    if (requestToken !== profileRequestToken) return;
    enrichmentFinished = false;
    $("profile-enrichment-result").hidden = false;
    $("profile-enrichment-result").replaceChildren();
    const message = document.createElement("p");
    message.textContent = "Profile research could not be completed right now. Retry research or skip to the conference graph.";
    $("profile-enrichment-result").append(message);
    $("continue-button").textContent = "Try profile research again";
    $("profile-status").textContent = "No profile topics were saved.";
  } finally {
    if (requestToken === profileRequestToken) {
      enrichmentInFlight = false;
      $("continue-button").disabled = false;
    }
  }
}
function invalidateProfileRequest() {
  const hadLookup = enrichmentInFlight || enrichmentFinished;
  profileRequestToken += 1;
  enrichmentInFlight = false;
  enrichmentFinished = false;
  $("continue-button").disabled = false;
  $("continue-button").textContent = "Find my interests";
  try { sessionStorage.removeItem(PROFILE_CONTEXT_KEY); } catch (_) { /* Clear cached topics if storage is available. */ }
  if (hadLookup) {
    $("profile-enrichment-result").replaceChildren();
    $("profile-enrichment-result").hidden = true;
    $("profile-status").textContent = "Profile inputs changed. Continue again to update topic suggestions.";
  }
}
$("profile-linkedin").addEventListener("input", invalidateProfileRequest);
$("profile-x").addEventListener("input", invalidateProfileRequest);
$("profile-consent").addEventListener("change", invalidateProfileRequest);
$("continue-button").onclick = async () => {
  if (enrichmentInFlight) return;
  if (enrichmentFinished) { goToExplore(); return; }
  const links = validatedInputs();
  if (!links) return;
  saveProfileLinks(links.linkedin, links.x);
  if (!$("profile-consent").checked) {
    try { sessionStorage.removeItem(PROFILE_CONTEXT_KEY); } catch (_) { /* Continue without saved personalization. */ }
    $("profile-status").textContent = "No profile research requested. Your conference graph is ready.";
    goToExplore();
    return;
  }
  if (!conferenceId) {
    $("profile-status").textContent = "Choose a conference before requesting profile research.";
    return;
  }
  await enrichProfile(links);
};
$("skip-button").onclick = event => {
  event.preventDefault();
  invalidateProfileRequest();
  goToExplore();
};
$("clear-button").onclick = () => {
  invalidateProfileRequest();
  $("profile-linkedin").value = "";
  $("profile-x").value = "";
  $("profile-consent").checked = false;
  $("linkedin-error").textContent = "";
  $("x-error").textContent = "";
  $("profile-linkedin").removeAttribute("aria-invalid");
  $("profile-x").removeAttribute("aria-invalid");
  $("profile-enrichment-result").replaceChildren();
  $("profile-enrichment-result").hidden = true;
  enrichmentFinished = false;
  $("continue-button").textContent = "Find my interests";
  try {
    sessionStorage.removeItem(STORAGE_KEY);
    sessionStorage.removeItem(PROFILE_CONTEXT_KEY);
    storageAvailable = true;
    $("profile-status").textContent = "Saved profile links and topics cleared from this browser session.";
  } catch (_) {
    storageAvailable = false;
    $("profile-status").textContent = "Could not access session storage. The fields are cleared from this page.";
  }
};
readSaved();
loadConference();
