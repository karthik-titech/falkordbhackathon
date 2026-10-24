"""Static contracts for the public conference graph interface."""

from pathlib import Path


STATIC = Path(__file__).resolve().parents[1] / "warmopen" / "static"


def test_conference_graph_is_bounded_accessible_and_keeps_list_view_collapsed():
    html = (STATIC / "try.html").read_text(encoding="utf-8")
    script = (STATIC / "try.js").read_text(encoding="utf-8")
    assert 'id="conference-graph" viewBox="0 0 520 520" role="group"' in html
    assert '<details class="graph-roster">' in html
    assert "Browse people as a list" in html
    assert "graph distance is not physical location" in html
    assert 'id="graph-focus"' in html and 'id="graph-search"' in html
    assert "const GRAPH_LIMIT = 48" in script
    assert 'role: "button"' in script and 'tabindex: "0"' in script
    assert 'event.key === "Enter" || event.key === " "' in script
    assert "No supported path in this view" in script
    assert "function edgeHasPublicCitation" in script
    assert "edge.evidence_ids.some" in script
    assert ".innerHTML" not in script


def test_profile_topics_are_explicit_and_actions_run_only_after_click():
    html = (STATIC / "try.html").read_text(encoding="utf-8")
    script = (STATIC / "try.js").read_text(encoding="utf-8")
    assert "Your interests" in html and "Looking for" in html
    assert "Compare with a public profile" in html
    assert "interest_topic_ids: Array.from(interestTopicIds)" in script
    assert "seeking_topic_ids: Array.from(seekingTopicIds)" in script
    assert "function assessConversation(targetId, refresh)" in script
    assert 'node("button", "Help me start a conversation"' in script
    assert 'research.addEventListener("click", () => assessConversation(targetId, true))' in script
    assert 'assessConversation(targetId, false)' not in script
    assert "assessment.rough_score" in script
    assert "Uncalibrated fit · starting estimate" in script
    assert "Based on limited conference information." in script
    assert '"Needs context"' in script
    assert "Try saying…" in script
    assert "What are you hoping to learn or discuss at this conference?" in script
    assert "No conference profile is treated as you." in script
    assert 'return $("graph-public-comparison").checked ? $("try-source").value : "";' in script
    assert "if (source) body.source = source;" in script
    assert "warmopen_profile_links" not in script
    assert "fetch(`/api/conferences/${encodeURIComponent(conferenceId)}/conversation`" in script


def test_public_mentions_are_collapsed_cited_and_not_scored():
    script = (STATIC / "try.js").read_text(encoding="utf-8")
    assert 'node("summary", "Public professional mentions")' in script
    assert "function renderMentions(container, mentions)" in script
    assert "item.published_at" in script and "item.excerpt" in script
    assert "item.tone" in script and "item.platform" in script and "item.url" in script
    assert "Tone describes the post, not a verified fact about the person." in script
    assert "Mention search is not available right now." in script
    assert "mentions.signals" not in script
    assert "reputation score" not in script.lower()


def test_graph_has_rotatable_3d_projection_and_2d_fallback():
    html = (STATIC / "try.html").read_text(encoding="utf-8")
    script = (STATIC / "try.js").read_text(encoding="utf-8")
    css = (STATIC / "welcome.css").read_text(encoding="utf-8")
    assert 'id="graph-3d-toggle" type="checkbox" checked' in html
    assert 'id="graph-rotate-hint"' in html
    assert "function graphPositions(graph, use3D" in script
    assert "const goldenAngle = Math.PI * (3 - Math.sqrt(5));" in script
    assert "graphYaw += dx" in script and "graphPitch = Math.max" in script
    assert 'addEventListener("pointerdown"' in script
    assert 'addEventListener("pointermove"' in script
    assert 'addEventListener("pointerup"' in script
    assert "event.stopImmediatePropagation()" in script
    assert "graphYaw = -0.35" in script and "graphPitch = 0.28" in script
    assert "graph-sphere-latitude" in script and "graph-shell-guide" in script
    assert "touch-action: none" in css
    assert "requestAnimationFrame" not in script and "setInterval" not in script
    assert "WebGL" not in script and "https://" not in script
