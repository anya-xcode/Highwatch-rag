---
name: Highwatch RAG
description: A clean document tool where every claim in an answer wears the highlighter colour of the source it came from.
colors:
  blue: "#2f5bd3"
  blue-deep: "#2750c0"
  blue-wash: "#e2e9fb"
  hl-1: "#fff0a0"
  hl-2: "#c9f0d3"
  hl-3: "#ffd9e4"
  hl-4: "#d6e6ff"
  hl-5: "#ffe3c7"
  ok: "#1f7a46"
  amber: "#8a5a00"
  amber-ink: "#6b4700"
  amber-wash: "#fdf3dc"
  amber-line: "#efd9a6"
  red: "#b42318"
  red-deep: "#962017"
  red-ink: "#8a1c12"
  red-wash: "#fdecea"
  red-line: "#f4c7c2"
  bg: "#ffffff"
  ink: "#1b1d21"
  ink-2: "#40444b"
  mute: "#6a6f78"
  excerpt-ink: "#2b2e34"
  line: "#e7e8ea"
  line-2: "#d9dbdf"
  panel: "#f7f7f8"
  hover: "#eff0f2"
typography:
  headline:
    fontFamily: "'Source Sans 3', system-ui, 'Segoe UI', sans-serif"
    fontSize: "23px"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "-0.012em"
  answer:
    fontFamily: "'Source Sans 3', system-ui, 'Segoe UI', sans-serif"
    fontSize: "17px"
    fontWeight: 400
    lineHeight: 1.65
  lede:
    fontFamily: "'Source Sans 3', system-ui, 'Segoe UI', sans-serif"
    fontSize: "16.5px"
    fontWeight: 400
    lineHeight: 1.6
  refusal:
    fontFamily: "'Source Sans 3', system-ui, 'Segoe UI', sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.55
  excerpt:
    fontFamily: "'Source Serif 4', Georgia, serif"
    fontSize: "15.5px"
    fontWeight: 400
    lineHeight: 1.65
  title:
    fontFamily: "'Source Sans 3', system-ui, 'Segoe UI', sans-serif"
    fontSize: "15px"
    fontWeight: 700
    lineHeight: 1.5
    letterSpacing: "-0.005em"
  title-sm:
    fontFamily: "'Source Sans 3', system-ui, 'Segoe UI', sans-serif"
    fontSize: "14px"
    fontWeight: 700
    lineHeight: 1.5
  wordmark:
    fontFamily: "'Source Sans 3', system-ui, 'Segoe UI', sans-serif"
    fontSize: "15.5px"
    fontWeight: 700
    lineHeight: 1.5
    letterSpacing: "-0.01em"
  body:
    fontFamily: "'Source Sans 3', system-ui, 'Segoe UI', sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
    fontFeature: "'tnum' 1"
  input:
    fontFamily: "'Source Sans 3', system-ui, 'Segoe UI', sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.5
  item:
    fontFamily: "'Source Sans 3', system-ui, 'Segoe UI', sans-serif"
    fontSize: "13.5px"
    fontWeight: 600
    lineHeight: "20px"
  label:
    fontFamily: "'Source Sans 3', system-ui, 'Segoe UI', sans-serif"
    fontSize: "13px"
    fontWeight: 600
    lineHeight: 1.5
  label-strong:
    fontFamily: "'Source Sans 3', system-ui, 'Segoe UI', sans-serif"
    fontSize: "14px"
    fontWeight: 600
    lineHeight: 1.5
  meta:
    fontFamily: "'Source Sans 3', system-ui, 'Segoe UI', sans-serif"
    fontSize: "12.5px"
    fontWeight: 400
    lineHeight: 1.5
  meta-sm:
    fontFamily: "'Source Sans 3', system-ui, 'Segoe UI', sans-serif"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: "17px"
  tag:
    fontFamily: "'Source Sans 3', system-ui, 'Segoe UI', sans-serif"
    fontSize: "11.5px"
    fontWeight: 600
    lineHeight: 1.5
  chip:
    fontFamily: "'Source Sans 3', system-ui, 'Segoe UI', sans-serif"
    fontSize: "10.5px"
    fontWeight: 700
    lineHeight: 1
  chip-source:
    fontFamily: "'Source Sans 3', system-ui, 'Segoe UI', sans-serif"
    fontSize: "12px"
    fontWeight: 700
    lineHeight: 1
rounded:
  xs: "4px"
  sm: "6px"
  md: "8px"
  lg: "10px"
  xl: "12px"
  pill: "999px"
  swipe: "5px 9px 6px 10px / 9px 5px 10px 6px"
  highlight: "0.35em 0.7em 0.4em 0.75em / 0.55em 0.35em 0.65em 0.4em"
spacing:
  xs: "6px"
  sm: "10px"
  md: "12px"
  lg: "16px"
  xl: "24px"
  xxl: "32px"
  xxxl: "48px"
  topbar: "56px"
  library: "304px"
  library-narrow: "272px"
  column: "720px"
components:
  top-bar:
    backgroundColor: "{colors.bg}"
    height: "56px"
    padding: "0 20px 0 18px"
  model-pill:
    textColor: "{colors.mute}"
    rounded: "{rounded.md}"
    height: "30px"
    padding: "0 11px 0 9px"
  status:
    textColor: "{colors.ink-2}"
    height: "30px"
    padding: "0 6px 0 8px"
  status-degraded:
    textColor: "{colors.amber}"
  status-not-ready:
    textColor: "{colors.red}"
  button:
    backgroundColor: "{colors.bg}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.md}"
    height: "32px"
    padding: "0 12px"
  button-hover:
    backgroundColor: "{colors.hover}"
  button-active:
    backgroundColor: "{colors.line}"
  button-disabled:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.mute}"
  button-wide:
    height: "36px"
    width: "100%"
  button-confirm:
    height: "26px"
    padding: "0 10px"
  button-danger:
    backgroundColor: "{colors.red}"
    textColor: "{colors.bg}"
  button-danger-hover:
    backgroundColor: "{colors.red-deep}"
  ask-button:
    backgroundColor: "{colors.blue}"
    textColor: "{colors.bg}"
    typography: "{typography.label-strong}"
    rounded: "{rounded.md}"
    height: "38px"
    padding: "0 14px 0 16px"
  ask-button-hover:
    backgroundColor: "{colors.blue-deep}"
  ask-button-disabled:
    backgroundColor: "{colors.blue-wash}"
    textColor: "{colors.blue-deep}"
  link-button:
    textColor: "{colors.blue}"
    typography: "{typography.label}"
  library-panel:
    backgroundColor: "{colors.panel}"
    width: "304px"
    padding: "18px 14px 16px"
  drop-zone:
    backgroundColor: "{colors.bg}"
    rounded: "{rounded.xl}"
    padding: "20px 12px 18px"
  drop-zone-dragover:
    backgroundColor: "{colors.blue-wash}"
  upload-item:
    backgroundColor: "{colors.bg}"
    rounded: "{rounded.lg}"
    padding: "9px 8px 9px 10px"
  document-row:
    textColor: "{colors.mute}"
    typography: "{typography.meta-sm}"
    rounded: "{rounded.md}"
    padding: "9px 8px"
  document-row-hover:
    backgroundColor: "{colors.hover}"
  document-name:
    textColor: "{colors.ink}"
    typography: "{typography.item}"
  document-remove:
    textColor: "{colors.mute}"
    rounded: "{rounded.sm}"
    size: "22px"
  document-remove-hover:
    backgroundColor: "{colors.red-wash}"
    textColor: "{colors.red}"
  citation-chip:
    backgroundColor: "{colors.hl-1}"
    textColor: "{colors.ink}"
    typography: "{typography.chip}"
    rounded: "{rounded.swipe}"
    height: "16px"
    padding: "0 4px"
  citation-chip-on-ink:
    backgroundColor: "rgba(27, 29, 33, 0.1)"
  citation-chip-source:
    typography: "{typography.chip-source}"
    height: "20px"
  highlight-mark:
    backgroundColor: "{colors.hl-1}"
    textColor: "{colors.ink}"
    rounded: "{rounded.highlight}"
    padding: "0.07em 0.2em 0.11em"
  highlight-mark-excerpt:
    padding: "0.05em 0.15em 0.08em"
  question:
    textColor: "{colors.ink}"
    typography: "{typography.headline}"
  answer:
    textColor: "{colors.ink}"
    typography: "{typography.answer}"
  refusal:
    textColor: "{colors.ink-2}"
    typography: "{typography.refusal}"
  example-card:
    backgroundColor: "{colors.bg}"
    rounded: "{rounded.xl}"
    padding: "20px 22px 18px"
  example-tag:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.mute}"
    typography: "{typography.tag}"
    rounded: "{rounded.pill}"
    padding: "2px 8px"
  sources-list:
    backgroundColor: "{colors.bg}"
    rounded: "{rounded.xl}"
  source-row:
    typography: "{typography.body}"
    height: "48px"
    padding: "10px 14px"
  source-row-lit:
    backgroundColor: "#fafafb"
  source-row-flash:
    backgroundColor: "{colors.blue-wash}"
  excerpt:
    textColor: "{colors.excerpt-ink}"
    typography: "{typography.excerpt}"
  budget-line:
    textColor: "{colors.mute}"
    typography: "{typography.meta}"
  pending-bar:
    backgroundColor: "{colors.panel}"
    rounded: "{rounded.xs}"
    width: "96px"
    height: "8px"
  notice:
    backgroundColor: "{colors.amber-wash}"
    textColor: "{colors.amber-ink}"
    typography: "{typography.body}"
    rounded: "{rounded.lg}"
    padding: "10px 12px"
  notice-error:
    backgroundColor: "{colors.red-wash}"
    textColor: "{colors.red-ink}"
  composer-field:
    backgroundColor: "{colors.bg}"
    rounded: "{rounded.xl}"
    height: "56px"
    padding: "0 9px 0 18px"
  composer-input:
    textColor: "{colors.ink}"
    typography: "{typography.input}"
  key-row:
    backgroundColor: "{colors.amber-wash}"
    textColor: "{colors.amber-ink}"
    rounded: "{rounded.lg}"
    padding: "10px 12px"
  key-input:
    backgroundColor: "{colors.bg}"
    rounded: "{rounded.md}"
    height: "32px"
    padding: "0 10px"
  toast:
    backgroundColor: "{colors.bg}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.lg}"
    padding: "12px 14px"
    width: "420px"
  kbd:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.xs}"
    padding: "3px 6px"
---

# Design System: Highwatch RAG

## Overview

**Creative North Star: "The Highlighter"**

Highwatch RAG looks like a clean, familiar document tool: a white page, a grey library down the left, a centred reading column, and a question box pinned at the bottom. Its personality lives in one device. Every claim in an answer is marked with a highlighter ink, and that ink belongs to the source the claim came from: the same colour sits on the claim's number, on the source row, on the matched phrase inside the quoted excerpt, and on the document in the library. A reviewer can trace any sentence to its evidence by colour alone.

Everything else stays quiet so the inks can do that work. Neutrals are cool greys on white, separated by 1px hairlines and a change of tone rather than by stacked cards; one action blue carries the primary button, links and focus; type is one humanist sans with a book serif kept for text quoted from documents. Density is that of a desktop productivity app: 14px base text, 13px controls, and a 720px reading column with 17px answer text.

This world replaced an earlier themed direction (map rulers, survey-sheet page strips, a woodland rail) that the user rejected as dull, odd, and wrong in colour and type, and asked instead for "clean and premium: a familiar app layout, very polished, personality in the details". It wears no costume: no textures, motifs or decorative colour, and no dark chat-bubble template. An answer reads as document text under its question heading, not as a message.

**Key Characteristics:**
- White ground, a cool grey library panel, 1px hairlines; flat except for the composer and the toast.
- Five pale highlighter inks used only to mark evidence; citation n wears the same ink everywhere it appears.
- Source Sans 3 for all UI and answers; Source Serif 4 only for quoted excerpts.
- One action blue for the Ask button, links, drag-over and focus.
- Irregular marker-tip corners on evidence (chips and highlight marks); regular 4–12px corners on everything else.
- One authored motion: highlights swipe in, left to right, when an answer lands.

## Colors

A near-monochrome interface in cool greys and one blue, with five pale highlighter inks that appear only where evidence is shown.

### Primary
- **Action Blue** (#2f5bd3): the Ask button, text links ("Open in Google Drive", "Add one to the library"), link buttons ("Show full answer", "Cancel"), the text caret, the 2px focus outline, the composer's focus border and the drop zone's drag-over border.
- **Pressed Blue** (#2750c0): hover on the Ask button and on the "Open in Google Drive" link; the label of the disabled Ask button.
- **Blue Wash** (#e2e9fb): the 3px focus ring around the composer and the API-key field, text selection, the drop zone while a file is dragged over it, the disabled Ask button, and the brief flash on a source row opened from a citation.

### Secondary
The highlighter inks. One per citation number: citation n uses ink ((n − 1) % 5) + 1, so citation 6 is yellow again. Text on an ink is always Ink.
- **Highlighter Yellow** (#fff0a0): citations 1, 6, 11. Also the highlighter stroke drawn across the logo mark and the sweep inside the "Searching…" bar.
- **Highlighter Mint** (#c9f0d3): citations 2, 7, 12.
- **Highlighter Rose** (#ffd9e4): citations 3, 8, 13.
- **Highlighter Sky** (#d6e6ff): citations 4, 9, 14.
- **Highlighter Peach** (#ffe3c7): citations 5, 10, 15.

### Tertiary
Status colours, always paired with an icon or a word, never with an ink.
- **Ready Green** (#1f7a46): the Ready status dot, the done icon on an upload, the success toast icon.
- **Amber** (#8a5a00): Degraded status text, the duplicate-upload icon and message. Warning surfaces use **Amber Ink** (#6b4700) text on **Amber Wash** (#fdf3dc) inside an **Amber Line** (#efd9a6) border: the answer warning notice and the API-key row. The degraded status dot is a one-off brighter amber (#d89b1a) so a 7px dot stays visible.
- **Red** (#b42318): failed and error text and icons, Not ready and Offline status, the filled Remove button (**Red Deep**, #962017, on hover). Error surfaces use **Red Ink** (#8a1c12) on **Red Wash** (#fdecea) inside a **Red Line** (#f4c7c2) border; Red Wash also backs the trash icon on hover.

### Neutral
- **White Ground** (#ffffff): page, thread, composer, cards, buttons, drop zone, upload items, toast; the text colour on blue and red fills.
- **Ink** (#1b1d21): primary text, headings, the logo square, chip numerals, and the 1.5px "lit" ring.
- **Soft Ink** (#40444b): the intro lede, refusal text, status label, icons inside buttons, keycap text.
- **Mute Grey** (#6a6f78): secondary text: counts, hints, document details, relevance labels, placeholders, the budget line.
- **Excerpt Ink** (#2b2e34): quoted excerpt text in the serif, a shade softer than Ink so the quote reads as a quote.
- **Hairline** (#e7e8ea): every structural 1px line: under the top bar, the library edge, list separators, the sources list, the example card, upload items.
- **Strong Hairline** (#d9dbdf): borders on controls (buttons, inputs, composer field, toast, keycaps), the idle status dot, the scrollbar thumb.
- **Library Grey** (#f7f7f8): the library panel, the Example tag, keycap and inline-code backgrounds, disabled buttons, the pending-bar track.
- **Hover Grey** (#eff0f2): hover on buttons, document rows and icon buttons.

### Named Rules
**The Evidence Ink Rule.** The highlighter inks mean "this came from a source". They appear only on evidence: highlight marks in answers, citation chips (in the answer, the sources list and the library) and the matched phrase in an excerpt. The only other yellow is the highlighter itself, drawn in the logo mark and in the sweep of the searching bar. Status, hover, selection, buttons and decoration never use an ink.

**The Same Colour Everywhere Rule.** Citation n wears ink ((n − 1) % 5) + 1 in every place it appears: its claim, its number, its source row, its excerpt phrase and its document's chip in the library. The ink comes from the number, never from position, file or relevance.

**The One Blue Rule.** Action blue is the only interactive colour, and the Ask button is the only solid blue fill on screen. Secondary actions are white buttons with a Strong Hairline border.

## Typography

**Body Font:** Source Sans 3 (variable, 200–900; fallback system-ui, Segoe UI, sans-serif)
**Quote Font:** Source Serif 4 (400 only; fallback Georgia, serif)
**Code:** the system monospace stack (ui-monospace, Cascadia Mono, Consolas) at 0.88em on a Library Grey 4px-radius tint, only for inline code inside answers.

Both faces are self-hosted woff2 files in latin and latin-ext subsets under the SIL Open Font License (licences shipped beside them), with `font-display: swap`; the latin Source Sans 3 file is preloaded.

**Character:** A plain, even humanist sans for everything the app says, and a book serif for everything a document says. The switch to serif is the signal that you are now reading the source, not the answer.

### Hierarchy
- **Headline** (600, 23px, 1.3, −0.012em, balanced wrapping): the current question heading and the intro heading; 20px at ≤820px. The largest text in the app; there is no display size.
- **Answer** (400, 17px, 1.65): answer text in the reading column; 16.5px inside the intro example, 16px at ≤820px.
- **Lede** (400, 16.5px, 1.6, max 64ch): the intro paragraph, in Soft Ink.
- **Refusal** (400, 16px, 1.55): the "not in your documents" reply, in Soft Ink.
- **Excerpt** (Source Serif 4, 400, 15.5px, 1.65, wrapping preserved): quoted source text in an opened source row.
- **Title** (700, 15px, −0.005em): the Library heading. **Title Small** (700, 14px): the Sources heading.
- **Wordmark** (700, 15.5px, −0.01em): "Highwatch RAG" beside the logo.
- **Body** (400, 14px, 1.5): base text, source rows, notices, toasts.
- **Input** (400, 16px): the composer question field (16px also keeps mobile browsers from zooming).
- **Item** (600, 13.5px, 20px line): document names in the library.
- **Label** (600, 13px): button labels, link buttons, the drop-zone instruction. **Label Strong** (600, 14px): the Ask button.
- **Meta** (400, 12.5px): counts, hints, library notes, the budget line, the remove-confirmation line. **Meta Small** (400, 12px, 17px line): the document details line.
- **Tag** (600, 11.5px): the Example tag. Keycaps use 600 11px.
- **Chip** (700, 10.5px, line 1): citation numerals in answers and the library. **Chip Source** (700, 12px): numerals in the sources list.

Earlier, folded exchanges drop their question to 15px/22px 600 and their answer to 15px/26px.

### Named Rules
**The Serif Means Quoted Rule.** Source Serif 4 is used only for text quoted from a document. Never for headings, answers, labels or UI.

**The Tabular Figures Rule.** The whole app sets tabular numerals, so relevance scores, counts and citation numbers line up.

## Layout

On desktop the app is a full-height two-column grid and the page itself never scrolls. A 56px top bar spans the width. The left column is the library panel (304px; 272px at ≤1100px), whose document list scrolls on its own. The right column is the work area: the thread scrolls above, and the composer sits pinned beneath it. Thread content and composer share one centred column, at most 720px wide, so the question box lines up with the answer above it.

**Spacing.** Small, slightly odd steps inside controls (6px between an icon and its text, 7–10px gaps, 9px row padding) and a wider rhythm between blocks: 12px between paragraphs and list items, 16px from question to answer, 24px before the example card and as the desktop side gutter, 32px before the Sources heading, 36px above and 32px below the hairline between exchanges, 48px at the top of the thread. Panel padding: thread 48px 24px 32px; composer 12px 24px 18px; library 18px 14px 16px.

**Exchanges.** Each question is appended to the thread. The previous exchange folds to its question and the first two lines of its answer (52px), with its sources and notices hidden behind a "Show full answer" / "Fold answer" link button; a Hairline separates exchanges. A new question scrolls so the previous exchange's divider sits at the top edge.

**Responsive.**
- **≤1100px:** the library narrows to 272px, and in source rows the file name stacks above its location (13px).
- **≤820px (tablets and phones):** one column, questions first. Order: top bar (sticky, 16px side padding), thread (24px 16px), composer (sticky to the bottom with a hairline above, 10px 16px 12px padding), then the library (hairline above, 20px 16px 28px). The page scrolls as a document. The model pill shows the provider only (icon and model id hidden, 28px tall); the Enter hint is hidden; source rows wrap with relevance dropping under the title (indented 36px); excerpts and their footers take 16px margins; the example answer clears its tag with 22px top padding; the toast spans the width at a 16px inset, 96px up, clear of the composer; the remove icon is always visible.
- **No hover (touch):** the remove icon is always visible and the details line reserves room for it.

### Named Rules
**The Questions First Rule.** At ≤820px the order is top bar, thread, composer, library: a reviewer can read the example and ask before scrolling past the upload controls.

**The One Column Rule.** The thread and the composer share the same centred 720px column; nothing in the work area breaks out of it.

## Elevation & Depth

Flat by default. Depth comes from tone (the white work area against the Library Grey panel) and from 1px hairlines. Two surfaces actually float: the composer field and the toast. Secondary buttons carry a 1px contact shadow so they read as pressable on both white and grey. Evidence never casts a shadow; its "lit" state is a ring.

### Shadow Vocabulary
- **Composer lift** (`box-shadow: 0 1px 2px rgba(27, 29, 33, 0.04), 0 8px 24px -10px rgba(27, 29, 33, 0.14)`): the composer field at rest. On focus it is replaced by the focus wash ring.
- **Toast float** (`box-shadow: 0 10px 30px -12px rgba(27, 29, 33, 0.3)`): the toast only.
- **Button contact** (`box-shadow: 0 1px 2px rgba(27, 29, 33, 0.05)`): secondary buttons; removed when disabled.
- **Focus wash ring** (`box-shadow: 0 0 0 3px #e2e9fb` with an Action Blue border): the composer field (focus-within) and the API-key input. Everywhere else focus is a 2px Action Blue outline, offset 2px.
- **Lit chip ring** (`box-shadow: 0 0 0 1.5px #1b1d21`): a citation chip that is hovered or lit, in the answer, the sources list or the library.
- **Lit mark ring** (`box-shadow: 0 0 0 2px <its ink>, 0 0 0 3px rgba(27, 29, 33, 0.25)`): a lit highlight mark grows 2px of its own ink and takes a faint ink rim.

The remove icon's `-8px 0 6px -2px` shadow in the row's own background colour is a fade over truncated text, not elevation.

### Named Rules
**The Two Lifts Rule.** Only the composer and the toast float. Every other surface sits flat on hairlines; a new panel or card gets a 1px Hairline border, not a shadow.

## Shapes

UI corners are regular and gentle, on a 4 / 6 / 8 / 10 / 12px ladder: 4px for keycaps, inline code and the pending bar; 6px for icon buttons (dismiss, remove); 8px for buttons, the model pill, inputs, document rows and the Ask button; 10px for upload items, notices, the API-key row and the toast; 12px for the drop zone, the example card, the sources list and the composer field. The Example tag is the one full pill; the status dot is a circle. One-offs: the drop-zone icon tile (34px, 9px radius) and the logo (28px square, 7px radius).

Evidence is irregular. Citation chips use the swipe radius (five-to-ten-pixel corners, different on every side), like the chisel tip of a marker. Highlight marks use an em-based uneven radius so the shape scales with the text, and `box-decoration-break: clone`, so every wrapped line of a claim gets its own ragged ends.

Borders are 1px solid throughout. The one dashed line is the idle drop zone (#c6c9cf), which turns solid Action Blue on drag-over.

Icons are 16px inline SVG on a 16-unit grid: 1.5 stroke, round caps and joins, no fill, current colour. The logo is an Ink rounded square holding an "H" whose two white uprights are joined by a Highlighter Yellow stroke tilted −6°.

### Named Rules
**The Marker Tip Rule.** Irregular corners belong to evidence only (chips and highlight marks). Controls, cards and inputs keep regular radii, and chips never take a regular radius.

## Components

### Top Bar
A plain 56px strip: logo and wordmark on the left (10px gap), model pill and status on the right (8px gap, 13px text), one Hairline beneath. Sticky at ≤820px.
- **Model pill:** 30px tall, 1px Hairline border, 8px radius, chip icon, provider in 600 Ink then " · model id" in Mute Grey, truncated with an ellipsis; a tooltip explains who writes the answers. With no model it reads "Extractive · no AI model".
- **Status:** a 7px dot and a 600 label in Soft Ink: "Checking…" (Strong Hairline dot), "Ready" (green dot), "Degraded" (amber text and dot), "Not ready" or "Offline" (red text and dot). The tooltip lists failing health checks or "All checks passed".

### Buttons
- **Secondary (default):** white, 1px Strong Hairline, 8px radius, 32px tall, 12px side padding, 600 13px, button contact shadow, Soft Ink icon. Hover Hover Grey; active Hairline; disabled Library Grey with Mute text, no shadow.
- **Wide:** full width, 36px, 10px above (Sync Google Drive). Busy: the sync icon spins and the label reads "Syncing…".
- **Ask (primary):** Action Blue fill, white 600 14px label with an up-arrow icon, 38px tall, 8px radius, no border. Hover Pressed Blue. Disabled (while asking): Blue Wash with a Pressed Blue label reading "Asking…".
- **Danger:** Red fill and border, white label, Red Deep on hover. Used only for the inline Remove confirmation, at the confirm size (26px, 10px padding, 12.5px).
- **Link button:** borderless Action Blue 600 13px text, underlined on hover ("Cancel", "Show full answer").
- **Icon buttons:** 22–24px, 6px radius, Mute icon; hover Hover Grey with Ink (dismiss) or Red Wash with Red (remove).
- **Focus:** 2px Action Blue outline, offset 2px, on every control.

### Library Panel
Library Grey, a Hairline on its right edge. Head: "Library" (Title) with a Mute count ("3 documents"). Then the drop zone, the Sync Google Drive button, an optional note, the upload queue, and the document list (Hairline above, scrolls).
- **Drop zone:** white, 1px dashed #c6c9cf, 12px radius, centred: a 34px Library Grey icon tile with an upload arrow, a 600 Ink instruction naming the accepted types from server config ("Drop PDF, DOCX, TXT or MD"), the size limit in Mute 12.5px, and a "Choose files" secondary button. Drag-over: solid Action Blue border on Blue Wash.
- **Drive note:** when Drive is not configured, the sync button is disabled and a 12.5px Mute note explains where to set it up.

### Upload Queue
White items, 1px Hairline, 10px radius, newest first, 6px apart. Grid: 16px state icon, name (600, truncated) over a status line, a 24px dismiss button. States: queued (clock, "Waiting…"), working (Action Blue spinning icon, "Uploading and indexing…"), done (green check, "Indexed · N chunks", removed after 8 seconds), duplicate (amber copy icon, amber message), error (red alert icon, red message, including client-side checks such as unsupported type, empty file or over the size limit). Files upload one at a time.

### Document Rows
Rows on the grey panel, 8px radius, 9px 8px padding, 2px apart; Hover Grey on hover or focus-within.
- **Anatomy:** 16px lead icon (file; Action Blue spinner while processing; red alert when failed), name in Item type, cited chips at the right of the name, and a Meta Small details line: "Indexed · 24 pages · 12 chunks · Upload", with "Processing" in 600 Soft Ink or "Failed" in 600 Red, and "Google Drive" as a link for Drive files. A failed row adds its error in 12px Red.
- **Cited chips:** after an answer, each document shows the citation numbers it supplied, each chip in its own ink, with a tooltip "Cited as 1, 2 in the latest answer". They light with the rest of that citation.
- **Remove:** a 22px trash icon floats over the end of the details line, hidden until the row is hovered or focused (always shown on failed or confirming rows, on touch, and at ≤820px). It opens an inline confirmation in the row: "Remove from the library?" (plus, for Drive files, that it returns on the next sync), then **Remove** (danger) and **Keep** (secondary), both 26px. Focus moves to Remove; Keep or Escape closes it and returns focus to the trash icon; Remove disables both and reads "Removing…".
- **Empty / error:** "No documents yet. Drop a file above or sync Google Drive." in Mute; a load failure in Red.

### Citation Chips
Small numbered tabs in their citation's ink: min 19px wide, 16px tall, 4px side padding, swipe radius, 700 10.5px Ink numerals. In the sources list they grow to min 24px by 20px with 12px numerals. A chip that sits inside a highlight of its own colour (the first chip of a claim) takes a 10% Ink tint instead of repeating the ink. In an answer a chip is a link with the label "Source n"; hovered or lit, it takes the 1.5px Ink ring.

### Highlighted Answer (signature)
The question (Headline) sits above the answer (Answer type, 12px between paragraphs, bullets indented 22px). Each cited claim is a highlight mark in the ink of its first citation, with its chips inside the mark at the end.

- **Where a highlight starts.** The claim is the last sentence fragment before its "[n]" (the text after the last `.`, `!`, `?`, `:` or `;` that is followed by a space, without leading punctuation). The mark starts at the first word of the longest run of three or more words the claim shares with that source's excerpt (case-insensitive, whole words) and runs to the citation, so the number always sits inside its own colour. Lead-in words before the shared phrase stay plain. With no shared run, the whole claim is marked.
- **What the excerpt marks.** In the opened source, only the shared phrase is marked, in the same ink, with slightly tighter padding (0.05em 0.15em 0.08em). The claim's highlight can be longer than the excerpt's; the excerpt shows exactly the words that matched.
- **Several citations on one claim** ("[1, 2]"): the mark takes the first number's ink; the first chip is tinted, the following chips keep their own inks.
- **Extractive answers** (no model): each "[n] passage" line becomes a two-column passage, the chip on the left and the quoted text beside it, without a mark.
- **Lit state:** hovering or focusing a mark or its chip lights every element of that citation at once: the mark's ring, the chip's ring, the source row (#fafafb with its chip ringed) and the library chip. Clicking (unless text is selected) opens that source, unfolding an earlier exchange if needed, scrolls it into view and flashes the row Blue Wash, which fades over 120ms.
- **Motion: the swipe.** When an answer lands, each mark's ink grows from left to right (background width 0% to 100%) over 520ms on `cubic-bezier(0.16, 1, 0.3, 1)`, staggered 120ms plus 140ms per mark, so the claims are inked in reading order. The example card plays it once on load. Under `prefers-reduced-motion: reduce` every animation and transition is off and highlights simply appear at rest.

**The Shared Phrase Rule.** A highlight starts at the first word of the longest phrase (three or more words) the claim shares with its source and runs through its citation chip; the excerpt marks only that shared phrase, in the same ink. With no shared phrase, the whole claim is marked.

**The One Swipe Rule.** The highlight swipe is the only authored motion. Nothing else slides, fades in or staggers; everything else is instant or a short functional transition.

### Example Card
The intro's labelled demonstration: Headline "Ask a question about your documents", a Lede, then a white card (1px Hairline, 12px radius, 20px 22px 18px padding) with an "Example" tag pinned top-right (pill, Library Grey, Tag type in Mute). Inside, a highlighted answer (16.5px, 64px right padding to clear the tag) and its sources as flat rows (a Hairline above, no outer border, no hover), the first one open.

### Sources List
"Sources" (Title Small) with a Mute count ("3 · 2 documents"), then one white list (1px Hairline, 12px radius) with Hairlines between rows. Each row is a disclosure: 48px minimum, 10px 14px padding, 12px gaps: chip, file name (600, truncated) and location in Mute ("p. 2 · Refunds", "pp. 3–4", or "chunk n" with the section), "relevance 0.82" right-aligned (value 600 Ink, two decimals), and a chevron that flips 180° when open. Hover and lit rows turn #fafafb. The open body holds the excerpt in the serif (margins 0 28px 16px 50px, aligned under the file name) and, for Drive files, an "Open in Google Drive" link (600 Action Blue, external icon). For model-written answers the first source opens by default.

### Answer States
- **Pending:** a 96px by 8px Library Grey track with a Highlighter Yellow segment sweeping across it, beside "Searching 16 chunks…" in 15px Mute.
- **Budget line:** under every answer, 12.5px Mute with a database icon: "Searched 3 documents · 16 chunks", plus "· no passage was relevant enough" after a refusal or "· quoted directly, no AI model" for extractive answers.
- **Refusal:** a Mute no-match icon and the reply in Refusal type, Soft Ink. No colour and no alarm: a calm answer, not an error.
- **Warning notice:** Amber Wash, Amber Line border, 10px radius, 10px 12px padding, alert icon, 14px Amber Ink. Shown above the answer when the model fails and excerpts are shown instead.
- **Error notice:** the same shape in Red Wash, Red Line and Red Ink, announced as an alert, when the request itself fails.
- **Empty library:** the intro shows "No documents yet. Add one to the library, then ask." with an info icon and a link to the library; the composer hint reads "Add a document to the library first."

### Composer
A 56px white field with a Strong Hairline border, 12px radius and the composer lift: the question input (Input type, Mute placeholder "Ask about your documents") with the Ask button inside on the right. Focus-within: Action Blue border and the 3px Blue Wash ring. While asking, the input and button are disabled. Below, a 12.5px Mute hint row: the library scope ("Searches 3 documents · 16 chunks") on the left, "Enter to ask" with a keycap on the right (keycap: 600 11px Soft Ink on Library Grey, Strong Hairline, 4px radius; hidden at ≤820px).

### API-Key Row
Appears above the composer field the first time the server answers 401. Amber Wash, Amber Line border, 10px radius, 10px 12px padding: "This server needs an API key." (600 13px Amber Ink), a 32px white password input (8px radius, Action Blue border and Blue Wash ring on focus), a "Use key" secondary button and a "Cancel" link button. Enter saves; Escape cancels.

### Toast
Fixed 24px from the bottom-right corner, at most 420px wide: white, Strong Hairline, 10px radius, toast float, 12px 14px padding, 14px text with a type icon (green check for success, red alert for error, Action Blue info for info). It rises 6px and fades in over 240ms and hides after 4.5 seconds (7–9 seconds for Drive sync results). At ≤820px it spans the width at a 16px inset, 96px up.

### Functional Motion
Besides the swipe, motion is feedback only: 120ms colour, border, opacity and ring transitions on controls; a 160ms chevron flip; the 240ms toast rise; spinners on syncing (900ms) and on working uploads and processing documents (1.1s); the pending sweep (1.3s). All of it stops under reduced motion, and smooth scrolling becomes instant.

## Do's and Don'ts

### Do:
- **Do** derive a citation's ink from its number, ((n − 1) % 5) + 1, and repeat that ink on its claim, chip, source row, excerpt phrase and library chip.
- **Do** start a highlight at the first word of the longest phrase the claim shares with its source (three or more words) and carry it through the citation chip; in the excerpt, mark only that shared phrase. With no shared phrase, mark the whole claim.
- **Do** keep text on an ink in Ink (#1b1d21), and tint a chip that sits on its own ink with 10% Ink instead of repeating the colour.
- **Do** separate regions with 1px hairlines and tone (White Ground against Library Grey), not with extra cards or shadows.
- **Do** set text quoted from a document in Source Serif 4 and everything else in Source Sans 3, with tabular numerals.
- **Do** confirm destructive actions inline in the row they affect (Remove / Keep) and return focus to the trigger when the person keeps the item.
- **Do** keep the highlight swipe as the only authored motion, and stop every animation and transition under reduced motion.
- **Do** put questions first at ≤820px: top bar, thread, sticky composer, then the library.

### Don't:
- **Don't** use a highlighter ink for status, hover, selection, buttons or decoration; the only non-evidence yellow is the highlighter drawn in the logo and in the searching bar.
- **Don't** render answers as chat bubbles or switch to a dark chat template; an answer is document text under its question.
- **Don't** dress the app in a theme (textures, rulers, motif strips, costume colours); the earlier Survey Sheet world was rejected for exactly that.
- **Don't** add a second solid accent button: the Ask button is the only blue fill, and red fills only the inline Remove confirmation.
- **Don't** give controls or cards the irregular swipe or highlight radius, or give chips a regular one.
- **Don't** add shadows beyond the composer lift, the toast float and the 1px button contact shadow.
- **Don't** introduce a display size above the 23px question heading.
