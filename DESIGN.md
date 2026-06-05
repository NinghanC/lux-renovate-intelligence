# Design

## Overview

Building Mission Readiness is a product UI for mission preparation, dossier review, evidence traceability, and source inspection. The design serves expert workflow: structured, restrained, dense, and clear about evidence boundaries.

Physical scene: a technical expert reviews a Luxembourg mission dossier on a desktop monitor in an office before field work, comparing source records, missing documents, and validation tasks under normal daytime lighting. This calls for a light, quiet workspace with crisp contrast and low visual drama.

## Color

Color strategy: restrained. Use cool-tinted neutrals for most of the surface, teal for primary action and source/evidence affordances, amber for partial or warning states, red-orange for missing or critical states, and blue-cyan only for informational or not-applicable states.

Use OKLCH tokens where possible:

```css
:root {
  --text: oklch(25% 0.017 210);
  --muted: oklch(51% 0.02 220);
  --subtle: oklch(94% 0.008 205);
  --line: oklch(88% 0.012 205);
  --surface: oklch(99% 0.004 205);
  --surface-soft: oklch(97.5% 0.006 205);
  --page: oklch(96.5% 0.006 205);
  --accent: oklch(45% 0.105 190);
  --accent-soft: oklch(96% 0.025 190);
  --warning: oklch(52% 0.13 70);
  --warning-soft: oklch(96% 0.04 80);
  --danger: oklch(49% 0.15 35);
  --danger-soft: oklch(94% 0.04 35);
}
```

Do not use pure black or pure white. Keep inactive controls neutral. Use accent color for primary actions, active tabs, selected map tools, evidence links, source chips, and focus rings.

## Typography

Use a product sans stack:

```css
font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
```

Type should be compact and readable:

- App title: 18px, 1.15 line-height, strong weight.
- Major dossier headings: 22px, 1.2 line-height.
- Section headings: 14 to 15px, strong weight.
- Labels and table headers: 12 to 13px, strong weight.
- Body and table content: 13 to 14px, 1.4 to 1.55 line-height.

Avoid display fonts, fluid heading scales, negative letter spacing, and oversized marketing-style type inside the app.

## Layout

Default structure is a two-column app shell: fixed-width sidebar for case controls, flexible workspace for context, dossier views, readiness tables, evidence, and system transparency.

Use predictable grids:

- Sidebar: 250 to 300px, vertical controls, upload and generation actions.
- Workspace: max width around 1320px with 18 to 24px page padding.
- Dossier hero and case header: two columns on desktop, single column below tablet widths.
- Data-heavy sections: horizontal scroll wrappers for readiness, follow-up, and inventory tables.
- Cards and panels: 8px radius, 1px borders, soft surface fills. Do not nest cards inside cards.

Spacing should vary by purpose: 8 to 10px within controls, 12 to 16px inside panels, 18 to 24px between major workspace sections.

## Components

Buttons use familiar product affordances:

- Primary button: teal fill, 42px height, 8px radius, icon plus text when command clarity benefits.
- Secondary and icon buttons: neutral surface, 1px line, 8px radius.
- Disabled state: reduced opacity and appropriate cursor.
- Active tab or toggle: teal fill for major selection, teal-tinted surface for secondary selection.

Form controls use full labels, 42px minimum select height, visible borders, and predictable focus states.

Evidence references use compact pill buttons with file name truncation and page or line locator separated visually. Long filenames must not resize the layout.

Status chips must include text labels:

- Found: green-tinted positive state.
- Partial: amber warning state.
- Missing or high priority: red-orange state.
- Unknown: neutral state.
- Not applicable: blue-cyan informational state.

Map controls should remain small, square, icon-led, and visually tied to the map surface.

## Motion

Keep motion functional and brief, 150 to 250ms. Use motion only for state feedback, hover, focus, loading, reveal, or scrolling to highlighted evidence. Avoid decorative page-load sequences. Respect reduced-motion preferences.

## Copy

Copy should be precise, bounded, and evidence-aware. Prefer labels like "Evidence available", "Requires expert validation", "Missing mission information", and "System transparency". Never imply that a readiness score is a safety, compliance, authorization, structural, environmental, energy, or legal conclusion.

Use concrete mission language instead of generic AI phrasing. Avoid promotional claims, chatbot language, and repeated explanations.

## Accessibility

Maintain WCAG AA contrast. All icon-only buttons need accessible names and hover/tooltips where appropriate. Tables need clear headers and readable horizontal scrolling. Tabs and interactive chips must be keyboard-accessible. Status information must be understandable without color.
