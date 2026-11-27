---
version: 1
slug: "frontend-index-html"
primary_target: "frontend/index.html"
related_targets: ["frontend/style.css","frontend/app.js"]
---

# Surface: main app screen (frontend/index.html)

Mode: operate. Audience: portfolio reviewers trying Highwatch RAG for a few minutes (see PRODUCT.md). Job: upload or sync documents, ask, verify the cited evidence, see an honest refusal. Constraints: vanilla HTML/CSS/JS served by FastAPI at /static, no build step, $0 (self-hosted free fonts, inline SVG icons, no CDN dependencies). Must keep: upload queue with per-file states, document list with status and inline delete, Drive sync, readiness status, model badge, inline API-key field, answer warnings, citations with Drive links, folded earlier exchanges. Light theme: reviewers on a laptop in daylight.

History: the first direction (Survey Sheet: map rulers, woodland rail, magenta page strips) was built and rejected by the user as dull, odd, and wrong in colour and type. The user asked for "clean & premium: familiar app layout, very polished, personality in the details" and picked Highlighter from the safer re-roll.

Memorable moment: every claim in an answer is highlighted in the colour of the source it came from.

## Direction contract

THESIS: Evidence you can see at a glance: each claim wears the highlighter colour of its source, and the same colour marks that source in the list and in the library. Refuses the dark chat-bubble template and any themed costume; the app is a clean, familiar document tool.

OWN-WORLD: White ground, ink #1b1d21, secondary #6a6f78, hairlines #e7e8ea, a light grey library panel #f7f7f8, action blue #2f5bd3 for buttons, links and focus. Highlighter inks are reserved for evidence only: yellow #fff0a0, mint #c9f0d3, rose #ffd9e4, sky #d6e6ff, peach #ffe3c7 (citation 1 to 5). Source Sans 3 for UI and answers, Source Serif 4 for quoted excerpts. 8–12px radii, 1px borders, soft shadows only on the composer and toasts.

STORY: The reviewer sees the library and how answers will look, adds a file or syncs Drive, asks, reads an answer whose highlighted claims point to numbered sources, opens the excerpt where the matched phrase carries the same highlight, and gets a calm "not in your documents" reply for an off-topic question.

FIRST VIEWPORT: Top bar (logo mark + name left; model pill and status right). Left 304px library panel: Library heading with count, white drop zone with Choose files, Sync Google Drive, documents with status and cited-colour chips. Centre column (720px): question heading, highlighted answer, Sources list with colour chips and relevance, first excerpt open. Empty state shows a labelled example of a highlighted answer. Composer pinned at the bottom; the blue Ask button is the primary action.

FORM: Highlighter, safer re-roll round 1, grounded candidate chosen by the user (assigned index suspended in the safer register); seed:4015200185699b5a. Signature interaction: hovering a highlighted claim or its number lights its source row, and clicking opens that excerpt. Motion grammar: one authored moment, the highlights swiping in left to right when an answer lands; everything else instant; reduced motion shows them at rest.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
