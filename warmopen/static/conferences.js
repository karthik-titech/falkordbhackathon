"use strict";
const $ = id => document.getElementById(id);
document.title = `${PRODUCT_NAME} · Conferences`;
$("conference-brand").textContent = PRODUCT_NAME;

function node(tag, text, className) {
  const item = document.createElement(tag);
  if (text !== undefined) item.textContent = text;
  if (className) item.className = className;
  return item;
}
function safeSource(url, text) {
  const link = node("a", text, "source-link");
  try {
    const parsed = new URL(url);
    if (["https:", "http:"].includes(parsed.protocol)) {
      link.href = parsed.href;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
    }
  } catch (_) { /* Unusable citations remain plain text. */ }
  return link;
}
function dateLabel(item) {
  if (!item.starts && !item.ends) return "Dates not listed";
  const format = value => {
    if (typeof value !== "string") return "Date not listed";
    const date = new Date(`${value.slice(0, 10)}T12:00:00Z`);
    return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat(undefined,
      {month: "short", day: "numeric", year: "numeric", timeZone: "UTC"}).format(date);
  };
  if (!item.starts) return format(item.ends);
  if (!item.ends || item.starts === item.ends) return format(item.starts || item.ends);
  return `${format(item.starts)} – ${format(item.ends)}`;
}
function card(item, evidence) {
  const article = node("article", undefined, "conference-card");
  const top = node("div", undefined, "conference-card-top");
  top.append(node("p", item.catalog_only ? "UPCOMING CONFERENCE" : "CONFERENCE", "eyebrow"));
  if (item.catalog_only) top.append(node("span", "Official listing", "catalog-pill"));
  article.append(top, node("h3", item.name));
  const date = node("p", dateLabel(item), "conference-date");
  if (item.official_url) date.append(document.createTextNode(" · "), safeSource(item.official_url, "Official event site"));
  else if (item.evidence_ids?.length && evidence[item.evidence_ids[0]]) {
    date.append(document.createTextNode(" · "), safeSource(evidence[item.evidence_ids[0]].url, "Event source"));
  }
  article.append(date);
  const counts = node("div", undefined, "conference-counts");
  const attendeeCount = item.confirmed_attendees_count || 0;
  const speakerCount = item.scheduled_speakers_count || 0;
  counts.append(node("p", `${attendeeCount} confirmed ${attendeeCount === 1 ? "attendee" : "attendees"}`));
  counts.append(node("p", `${speakerCount} scheduled ${speakerCount === 1 ? "speaker" : "speakers"}`));
  article.append(counts);
  if (!attendeeCount) article.append(node("p", "No confirmed attendee list imported yet.", "conference-empty"));
  const button = node("a", "Choose this conference", "primary-link");
  button.href = `/start?conference=${encodeURIComponent(item.id)}`;
  article.append(button);
  return article;
}
async function init() {
  try {
    const response = await fetch("/api/conferences");
    if (!response.ok) throw new Error("Could not load conferences.");
    const data = await response.json();
    const items = data.items || [];
    $("conference-list").replaceChildren(...items.map(item => card(item, data.evidence || {})));
    $("conference-status").textContent = items.length
      ? `${items.length} ${items.length === 1 ? "conference" : "conferences"} in the directory.`
      : "No conferences are listed yet.";
  } catch (_) {
    $("conference-status").textContent = "Conference listings are temporarily unavailable.";
  }
}
init();
