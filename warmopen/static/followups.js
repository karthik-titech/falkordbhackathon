"use strict";
// Private action sessions are kept separate from public profile exploration.
const followupPlanner = document.getElementById("followup-planner");
function parkFollowupPlanner() {
  const parking = document.getElementById("followup-parking");
  if (followupPlanner.parentElement !== parking) parking.append(followupPlanner);
}
function mountFollowupPlanner(container, target) {
  container.append(followupPlanner);
  const name = names[target] || conferenceRoster[target]?.name || "this person";
  followupPlanner.querySelector("#followup-command").placeholder = `Remind me to follow up with ${name} via LinkedIn…`;
}
let privateActionSession = null, followupItems = [], actionBusy = false;
const ACTION_SESSION_KEY = "warmopen_action_session_v1";
async function actionSession(create = true) {
  if (privateActionSession) return privateActionSession;
  const own = profileTopicContext?.profile_session;
  if (own?.id && own?.token) privateActionSession = {id: own.id, token: own.token};
  if (!privateActionSession) {
    try { privateActionSession = JSON.parse(sessionStorage.getItem(ACTION_SESSION_KEY) || "null"); }
    catch (_) { /* A new private session can be created on demand. */ }
  }
  if (!privateActionSession && create) {
    const result = await api("/api/actions/session", {});
    privateActionSession = result.session;
    try { sessionStorage.setItem(ACTION_SESSION_KEY, JSON.stringify(privateActionSession)); } catch (_) { /* Keep the token in memory. */ }
  }
  return privateActionSession;
}
async function followupApi(fields, create = true) {
  const session = await actionSession(create);
  if (!session) return {items: []};
  const conferenceId = new URLSearchParams(location.search).get("conference");
  const response = await fetch("/api/actions", {method: "POST", headers: {"Content-Type": "application/json", "X-Owner-Token": session.token},
    body: JSON.stringify({session_id: session.id, conference_id: conferenceId, ...fields})});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "Could not update follow-ups.");
  return result;
}
function renderFollowups() {
  const list = $("saved-followups");
  list.replaceChildren();
  if (!followupItems.length) list.append(node("p", "No follow-ups saved in this session yet.", "followup-note"));
  for (const item of followupItems) {
    const card = node("article", undefined, `saved-followup ${item.status === "done" ? "followup-done" : ""}`);
    card.append(node("strong", `${item.status === "done" ? "✓ " : ""}${item.target_name} · ${item.channel === "unspecified" ? "Follow up" : item.channel}`));
    card.append(node("p", item.due_at ? `${new Date(item.due_at) <= new Date() && item.status !== "done" ? "Due · " : ""}${new Date(item.due_at).toLocaleString()}` : "No reminder time set", "followup-note"));
    card.append(node("p", item.note, "followup-note"));
    const actions = node("div", undefined, "followup-actions");
    const view = node("button", "View person", "followup-action"); view.type = "button";
    view.onclick = () => activateGraphNode(item.target);
    actions.append(view);
    if (item.status !== "done") {
      const done = node("button", "Mark done", "followup-action"); done.type = "button";
      done.onclick = async () => {
        done.disabled = true;
        try { followupItems = (await followupApi({operation: "done", action_id: item.id})).items; renderFollowups(); if (conferenceGraph) renderConferenceGraph(false, true); }
        catch (error) { $("followup-status").textContent = error.message; done.disabled = false; }
      };
      actions.append(done);
    }
    if (item.due_at) {
      const calendar = node("button", "Add to calendar", "followup-action"); calendar.type = "button";
      calendar.onclick = () => {
        const stamp = value => new Date(value).toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
        const escape = value => value.replace(/\\/g, "\\\\").replace(/\n/g, "\\n").replace(/[,;]/g, match => "\\" + match).replace(/\r/g, "");
        const content = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Conference Followups//EN", "BEGIN:VEVENT", `UID:${item.id}@followup.local`, `DTSTAMP:${stamp(new Date())}`, `DTSTART:${stamp(item.due_at)}`, `DURATION:PT15M`, `SUMMARY:${escape("Follow up with " + item.target_name + " via " + item.channel)}`, "BEGIN:VALARM", "TRIGGER:PT0M", "ACTION:DISPLAY", "DESCRIPTION:Follow up", "END:VALARM", "END:VEVENT", "END:VCALENDAR", ""].join("\r\n");
        const url = URL.createObjectURL(new Blob([content], {type: "text/calendar"}));
        const link = node("a"); link.href = url; link.download = "conference-follow-up.ics"; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
      };
      actions.append(calendar);
    }
    card.append(actions); list.append(card);
  }
}
async function loadFollowups() {
  try { followupItems = (await followupApi({operation: "list"}, false)).items; renderFollowups(); if (conferenceGraph) renderConferenceGraph(false, true); }
  catch (error) { $("followup-status").textContent = error.message; }
}
async function saveFollowup() {
  if (actionBusy) return;
  actionBusy = true; $("save-followup").disabled = true;
  try {
    const text = $("followup-command").value.trim();
    let due = $("followup-due").value;
    // Resolve simple calendar phrases in the requester's local timezone.
    if (!due && /\b(?:tomorrow|today)\b/i.test(text)) {
      const date = new Date(); if (/\btomorrow\b/i.test(text)) date.setDate(date.getDate() + 1);
      const time = text.match(/\bat (\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b/i);
      let hour = time ? Number(time[1]) : 9;
      if (time?.[3]) hour = hour % 12 + (time[3].toLowerCase() === "pm" ? 12 : 0);
      if (hour > 23 || Number(time?.[2] || 0) > 59) throw new Error("Choose a valid reminder time.");
      date.setHours(hour, Number(time?.[2] || 0), 0, 0);
      due = new Date(date - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
      $("followup-due").value = due;
    }
    const result = await followupApi({operation: "save", text, request_id: crypto.randomUUID(), target: $("graph-focus").value || conferenceGraph?.center_id,
      due_at: due ? new Date(due).toISOString() : null});
    followupItems = result.items; renderFollowups(); if (conferenceGraph) renderConferenceGraph(false, true);
    const item = followupItems.find(item => item.id === result.saved_id);
    const reply = result.reply + (item?.due_at ? ` Reminder set for ${new Date(item.due_at).toLocaleString()}.` : " It’s in your follow-up list; no reminder time is set.");
    $("followup-status").textContent = reply;
    $("followup-due").value = "";
  } catch (error) { $("followup-status").textContent = error.message; }
  finally { actionBusy = false; $("save-followup").disabled = false; }
}
