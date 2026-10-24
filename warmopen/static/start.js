"use strict";
const $ = id => document.getElementById(id);
const STORAGE_KEY = "warmopen_profile_links";
const params = new URLSearchParams(window.location.search);
const conferenceId = params.get("conference") || "";
document.title = `${PRODUCT_NAME} · Conference`;
$("start-brand").textContent = PRODUCT_NAME;
let storageAvailable = true;

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
    return {value: `https://www.linkedin.com/in/${match[1]}`, error: ""};
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
$("continue-button").onclick = () => {
  const linkedin = validateLinkedIn($("profile-linkedin").value);
  const x = validateX($("profile-x").value);
  $("linkedin-error").textContent = linkedin.error;
  $("x-error").textContent = x.error;
  $("profile-linkedin").setAttribute("aria-invalid", String(Boolean(linkedin.error)));
  $("profile-x").setAttribute("aria-invalid", String(Boolean(x.error)));
  if (linkedin.error || x.error) {
    (linkedin.error ? $("profile-linkedin") : $("profile-x")).focus();
    return;
  }
  if (storageAvailable) {
    try {
      if (linkedin.value || x.value) {
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify({linkedin: linkedin.value, x: x.value}));
      } else {
        sessionStorage.removeItem(STORAGE_KEY);
      }
      $("profile-status").textContent = linkedin.value || x.value
        ? "Saved in this browser session. Profile lookup is not connected yet."
        : "No profile links saved. Profile lookup is not connected yet.";
    } catch (_) {
      $("profile-status").textContent = "Could not save links in this browser session. Continuing without them.";
    }
  } else {
    $("profile-status").textContent = "Continuing without saved links. Profile lookup is not connected yet.";
  }
  window.setTimeout(goToExplore, 250);
};
$("skip-button").onclick = event => {
  event.preventDefault();
  goToExplore();
};
$("clear-button").onclick = () => {
  $("profile-linkedin").value = "";
  $("profile-x").value = "";
  $("linkedin-error").textContent = "";
  $("x-error").textContent = "";
  $("profile-linkedin").removeAttribute("aria-invalid");
  $("profile-x").removeAttribute("aria-invalid");
  try {
    sessionStorage.removeItem(STORAGE_KEY);
    storageAvailable = true;
    $("profile-status").textContent = "Saved profile links cleared from this browser session.";
  } catch (_) {
    storageAvailable = false;
    $("profile-status").textContent = "Could not access session storage. The fields are cleared from this page.";
  }
};
readSaved();
loadConference();
