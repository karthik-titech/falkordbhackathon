"use strict";
const $ = id => document.getElementById(id);
document.title = `Owner approvals · ${PRODUCT_NAME}`;
$("product-name").textContent = `${PRODUCT_NAME} · FalkorDB`;
let owner = new URLSearchParams(location.search).get("owner") || "", token = "", polling = false, active = false;
$("owner-id").value = owner;
function restore() {
  try { token = sessionStorage.getItem(`warmopen-owner:${owner}`) || ""; } catch (_) { token = ""; }
  $("owner-token").value = token;
}
restore();
async function api(path, body) {
  const response = await fetch(path, {method: body ? "POST" : "GET",
    headers: {"X-Owner-Token": token, "Content-Type": "application/json"},
    ...(body ? {body: JSON.stringify(body)} : {})});
  const data = await response.json();
  if (data.mode === "recorded") $("mode-banner").hidden = false;
  if (!response.ok) throw new Error(data.error || "Request failed");
  return data;
}
async function pending() {
  if (polling || !active) return;
  polling = true;
  try {
    const data = await api(`/api/owner/${encodeURIComponent(owner)}/pending`);
    $("headline").textContent = data.items.length ? `Approve what ${data.items[0].requester_name} can see.` : "No pending requests.";
    $("pending").replaceChildren();
    for (const item of data.items) {
      const row = $("approval-row").content.cloneNode(true);
      row.querySelector("h2").textContent = `${item.requester_name} → ${item.target_name}`;
      const goal = item.goal === "invest" ? "Invest" : "Product sales proposal";
      row.querySelector("p").textContent = `${goal} · Request ${item.request_id} · Asked: ${item.asked ? "yes" : "no"}`;
      for (const button of row.querySelectorAll("button")) {
        const scope = button.dataset.scope;
        button.disabled = item[`${scope}_granted`];
        if (button.disabled) button.textContent = `${scope === "reveal" ? "Reveal" : "Reachability"} approved`;
        button.onclick = async () => {
          button.disabled = true;
          try {
            await api("/api/grants", {owner, requester: item.requester, request_id: item.request_id, scope});
            await pending();
          } catch (error) { $("owner-status").textContent = error.message; button.disabled = false; }
        };
      }
      $("pending").append(row);
    }
    $("owner-status").textContent = data.items.length ? "Pending requests refreshed. Grants expire after 15 minutes." : "No requests yet. Ask this owner from the requester page.";
  } catch (error) { $("owner-status").textContent = error.message; }
  finally { polling = false; }
}
$("owner-form").onsubmit = event => {
  event.preventDefault(); owner = $("owner-id").value.trim(); token = $("owner-token").value;
  try { sessionStorage.setItem(`warmopen-owner:${owner}`, token); } catch (_) { /* The token stays in this page's memory. */ }
  active = true; pending();
};
active = !!(owner && token);
if (active) pending();
setInterval(pending, 2000);
