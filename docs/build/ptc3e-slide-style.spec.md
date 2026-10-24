RISK: standard
BUILDER: sol
SCOPE: warmopen/static
PROTECTED: tests/conftest.py, tests/test_ptc1_core.py, tests/test_ptc1b_fixes.py, tests/test_ptc2_score.py, tests/test_ptc2b_jev_shape.py, tests/test_ptc3_app.py, tests/test_ptc3b_polish.py, tests/test_ptc3c_demo_polish.py, tests/test_ptc3e_slide_style.py
FORBID: git, env-keys, deps

GOAL
After this chunk, the requester and owner pages look like Karthik's reference slides: each state reads like one projector slide with a kicker, one big heavy headline, a monospace subline, the warm path drawn as line art, marked three-column reasons, and a numbered five-step track along the bottom. Behavior, API calls and every existing id stay the same.

INTENT ANCHOR
A judge at the back of the room can read the current step, the headline and the path from the projector without squinting.

CONTEXT
- Parent specs still bind: stdlib server, hand-written HTML/CSS/JS, NO external scripts, stylesheets, fonts or CDNs, no innerHTML with graph strings, links only http/https, UI copy says "uncalibrated fit" and never "probability" or "chance". Element ids and copy pinned by tests/test_ptc3_app.py, test_ptc3b_polish.py, test_ptc3c_demo_polish.py and test_ptc3e_slide_style.py must survive.
- Projector 1280 px is the primary target; phone 390 px must still have no horizontal page overflow (ptc3d).

DESIGN TOKENS (binding)
- Colors as CSS custom properties on :root: --paper #ECEBE7 (page), --ink #171717 (headlines, rules, filled squares), --graphite #55554F (second headline line, body), --olive #46522F (current step, filled-column items, primary button), --muted #8F8D86 (empty-column items, future steps), --rule #1F1F1F (thin rules, 1.5px). Panels are not cards: no shadows, no rounded corners, no panel backgrounds; sections are separated by whitespace and thin rules.
- Type: headline font-family -apple-system, "SF Pro Display", "Helvetica Neue", Arial, sans-serif; weight 800; letter-spacing -0.03em; size clamp(40px, 5.2vw, 72px); line-height 1.02. Body: same family, weight 500, 18-20px at 1280. Labels: ui-monospace, "SF Mono", Menlo, monospace; 11-12px; uppercase; letter-spacing 0.16em. No @font-face, no @import.
- Buttons: rectangular (border-radius 0), monospace uppercase label; primary = olive fill with paper text; secondary = 1.5px ink outline. Inputs: no box, a 1.5px bottom rule only, monospace label above.

LAYOUT (requester page, 1280)
  ◆ 02 · ASK                                         WARM OPEN · FALKORDB   02 / 05
  A warm path to Garry Tan.                          <- h1#headline (ink)
  Owner B can reach them in 2 hops.                  <- second line (graphite), optional
  INVEST · CLOSING KEYNOTE · AI ENGINEER WORLD'S FAIR <- monospace subline
  [requester ___] [speaker filter ___] [target ___] [goal ___]   [FIND A PATH]
  path line art (svg#path-view): requester and target as filled square blocks, owners/contacts as small squares, solid ink spans for approved or public hops, dashed span labeled "asked" (keep stroke-dasharray), monospace labels above nodes, category under each span; caption below in body text.
  ■ SUPPORTS ______   ◩ AGAINST ______   □ WOULD IMPROVE ______   (fit card; "uncalibrated fit" stays as the section label; band shown large)
  Owners: one row per owner, "Owner B (demo)   reachable · 2 hops · tie 0.63   [REVEAL]"
  Openers: three numbered quotes in body size, monospace SOURCE link and the cited claim under each.
  Agent timeline (ol#agent-timeline): narrow right column in monospace, small, newest last.
  bottom: ol#step-track  ■──■──■(olive)──□──□   01 FIND  02 ASK  03 APPROVE  04 SCORE  05 OPEN
Owner page: same tokens; kicker "◆ OWNER APPROVALS"; h1 "Approve what <requester_name> can see." once a row exists (else "No pending requests."); rows as above with the two approve buttons.

WHAT EXISTS
- warmopen/static/index.html:11 header block "CONFERENCE CONNECTIONS / the app"; panels as rounded cards (lines 14-35).
- warmopen/static/style.css: card styling, .workspace grid with min-width: 0 children (ptc3d).
- warmopen/static/app.js draw(): SVG path with circles and the dashed "asked" edge (ptc3c).
- warmopen/static/owner.html, warmopen/static/owner.js: owner approvals page.

TASKS
T1. style.css: replace the stylesheet with the token system above. Keep #mode-banner visible only in recorded mode, styled as a monospace ink bar "RECORDED RUN" at the top. Keep .workspace children min-width: 0 (ptc3d). Add @media (prefers-reduced-motion: reduce) to disable the path draw-in.
T2. index.html: add <p id="kicker">, <h1 id="headline">, a subline element, and <ol id="step-track"> with five <li data-step="find|ask|approve|score|open"> in that order, each holding the square marker and "01 FIND" style label. Keep every existing id. Remove the old "CONFERENCE CONNECTIONS / the app" header block; the product name moves into the top-right counter text "WARM OPEN · FALKORDB".
T3. app.js: compute the current step from progress (no request -> "find"; request created -> "ask"; route revealed or a public route exists and owner asked -> "approve"; fit scored -> "score"; openers written or sent -> "open"); set aria-current="step" on the current li, mark done steps, and set #kicker to "◆ 0N · STEP" and the counter to "0N / 05". Set #headline per state in sentence case ending with a period, e.g. "Who do you want to meet?", "A warm path to <target>.", "<owner> can reach <target>.", "Your fit with <target>.", "Three ways to open." Use textContent only. Redraw svg#path-view in the line-art style: one draw-in animation of the spans on reveal (stroke-dashoffset), skipped under reduced motion. Keep every behavior and string the frozen tests check (abstention phrases, "asked", stroke-dasharray, "uncalibrated fit").
T4. owner.html and owner.js: apply the same tokens and kicker/headline pattern; keep owner-form, owner-id, owner-token, pending ids and button labels "Approve reachability" and "Approve reveal".

FROZEN CONTRACT
tests/test_ptc3e_slide_style.py (PROTECTED; 4 of 6 cases FAIL now), plus every earlier frozen file.

DONE-GATE
- (T1-T4) `python3 -m pytest -q tests` all green against a live FalkorDB (60 tests).
- (T1-T4) Gate seat: headless Firefox walk-through screenshots at 1280 match the reference traits; phone check scrollWidth <= 390.
- Every task T1-T4 reported done or explicitly not done.

ASSUMPTIONS AND OPEN QUESTIONS
- A1 The demo laptop is a Mac, so SF Pro renders; other systems fall back to Helvetica Neue or Arial.
- Q1 Exact spacing is the builder's choice within the tokens; generous whitespace like the slides.

CONSTRAINTS: work only inside warmopen/static. No git. No network. Do not edit tests/. Print files changed and deviations.

C-ENV. Build environment (spec author, 2026-10-24): laptop tree, no FalkorDB, stdlib only. Do not install anything. Static tests in tests/test_ptc3e_slide_style.py run without FalkorDB: `python3 -m pytest -q tests/test_ptc3e_slide_style.py` (pytest is present on the laptop). The gate seat runs the full suite in Daytona and the browser checks.
