"use strict";
// Private action sessions are kept separate from public profile exploration.
let privateActionSession = null, followupItems = [], actionBusy = false, voiceRecorder = null;
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
        catch (error) { $("voice-assistant-reply").textContent = error.message; done.disabled = false; }
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
  catch (error) { $("voice-assistant-reply").textContent = error.message; }
}
async function saveSpokenFollowup(speak = false) {
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
    $("voice-assistant-reply").textContent = reply;
    $("followup-due").value = "";
    const playback = listenButton(() => reply); $("voice-reply-playback").replaceChildren(playback);
    if (speak) playback.querySelector("button").click();
  } catch (error) { $("voice-assistant-reply").textContent = error.message; }
  finally { actionBusy = false; $("save-followup").disabled = false; }
}
async function recordFollowup() {
  if (voiceRecorder) { voiceRecorder.stop(); return; }
  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) { $("voice-assistant-reply").textContent = "Microphone recording is unavailable here. Type your request below."; return; }
  const button = $("record-followup"); button.disabled = true;
  let stream = null;
  try {
    stopSpeech();
    const session = await actionSession();
    stream = await navigator.mediaDevices.getUserMedia({audio: true});
    const format = ["audio/webm", "audio/mp4", "audio/ogg"].find(type => MediaRecorder.isTypeSupported(type));
    if (!format) throw new Error("This browser cannot record a supported audio format. Type your request instead.");
    const recorder = new MediaRecorder(stream, {mimeType: format});
    const chunks = []; voiceRecorder = recorder;
    recorder.ondataavailable = event => { if (event.data.size) chunks.push(event.data); };
    recorder.onstop = async () => {
      clearTimeout(timer); stream.getTracks().forEach(track => track.stop()); voiceRecorder = null;
      button.textContent = "Transcribing…"; button.disabled = true;
      try {
        const blob = new Blob(chunks, {type: format});
        if (!blob.size || blob.size > 5000000) throw new Error("Keep the voice note short, then try again.");
        const response = await fetch("/api/transcribe", {method: "POST", headers: {"Content-Type": format, "X-Profile-Session": session.id, "X-Owner-Token": session.token}, body: blob});
        const result = await response.json(); if (!response.ok) throw new Error(result.error || "Could not transcribe. Type your request instead.");
        $("followup-command").value = result.text;
        await saveSpokenFollowup(true);
      } catch (error) { $("voice-assistant-reply").textContent = error.message; }
      finally { button.disabled = false; button.textContent = "🎙 Add a voice note"; }
    };
    recorder.start();
    const timer = setTimeout(() => { if (recorder.state === "recording") recorder.stop(); }, 20000);
    button.textContent = "Stop & save"; button.disabled = false;
    $("voice-assistant-reply").textContent = "Listening… say who to follow up with and how. Tap Stop & save when you’re done (20 seconds max).";
  } catch (error) {
    stream?.getTracks().forEach(track => track.stop()); voiceRecorder = null;
    $("voice-assistant-reply").textContent = error.name === "NotAllowedError" ? "Microphone permission was declined. You can type your request below." : error.message;
    button.disabled = false; button.textContent = "🎙 Add a voice note";
  }
}
