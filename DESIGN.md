---
name: Stock Analysis Engine
description: An explainable stock-analysis engine that answers with ranges, told in a bright story world and worked in a dim instrument world.
colors:
  accent-blue: "#2a78d6"
  accent-blue-deep: "#1c5cab"
  accent-blue-lit: "#3987e5"
  accent-blue-lit-strong: "#6aa6ee"
  accent-wash-light: "#e8f1fc"
  story-ground: "#f6f8fb"
  story-navy: "#0b1b33"
  story-navy-2: "#3a4862"
  story-navy-3: "#56647c"
  window-navy: "#0b1220"
  window-surface: "#111a2b"
  window-surface-2: "#172238"
  window-line: "#1f2b42"
  dim-page: "#1c2028"
  dim-surface: "#242a34"
  dim-surface-2: "#2b323d"
  dim-surface-3: "#363e4b"
  dim-ink: "#eef1f6"
  dim-ink-2: "#b7bfcc"
  dim-ink-3: "#939cab"
  dim-line: "#333b47"
  dim-line-strong: "#46505f"
  light-page: "#f4f5f7"
  light-surface: "#ffffff"
  light-surface-2: "#f2f4f7"
  light-ink: "#0f1419"
  light-ink-2: "#48505c"
  light-ink-3: "#6b7380"
  light-line: "#e4e7ec"
  light-line-strong: "#cfd4dc"
  dark-page: "#111418"
  dark-surface: "#181c22"
  dark-surface-2: "#1f242c"
  dark-ink: "#eef1f5"
  dark-line: "#2a303a"
  series-orange: "#eb6834"
  series-orange-dim: "#d95926"
  series-green: "#1baf7a"
  series-green-dim: "#199e70"
  up-light: "#0a7d32"
  up-dim: "#46d27a"
  down-light: "#c42b2b"
  down-dim: "#ff7a7a"
  warn-light: "#8a5800"
  warn-dim: "#f3c044"
  status-good: "#0ca30c"
  status-warning: "#fab219"
  status-critical: "#d03b3b"
  status-neutral: "#8a919c"
  glow-blue: "#6fb0ff"
  glow-aqua: "#5fe0b8"
  glow-peach: "#ffb08a"
  fan-high: "#0f7a58"
  fan-low: "#c2410c"
typography:
  display:
    fontFamily: "Geist, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "clamp(2.4rem, 4.4vw, 4.1rem)"
    fontWeight: 700
    lineHeight: 1.03
    letterSpacing: "-0.04em"
  headline:
    fontFamily: "Geist, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "clamp(1.9rem, 3.6vw, 3rem)"
    fontWeight: 700
    lineHeight: 1.06
    letterSpacing: "-0.035em"
  headline-step:
    fontFamily: "Geist, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "clamp(1.5rem, 2.4vw, 2rem)"
    fontWeight: 700
    lineHeight: 1.12
    letterSpacing: "-0.03em"
  title:
    fontFamily: "Geist, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "clamp(1.45rem, 2.4vw, 1.9rem)"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.025em"
  title-card:
    fontFamily: "Geist, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "1rem"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  body:
    fontFamily: "Geist, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.55
  body-story:
    fontFamily: "Geist, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "1.06rem"
    fontWeight: 400
    lineHeight: 1.65
  label:
    fontFamily: "Geist, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "0.78rem"
    fontWeight: 500
    lineHeight: 1.4
  figure-hero:
    fontFamily: "Geist Mono, ui-monospace, SF Mono, Consolas, monospace"
    fontSize: "clamp(1.9rem, 3.4vw, 2.6rem)"
    fontWeight: 500
    lineHeight: 1
    letterSpacing: "-0.03em"
    fontFeature: "tnum"
  figure:
    fontFamily: "Geist Mono, ui-monospace, SF Mono, Consolas, monospace"
    fontSize: "1.55rem"
    fontWeight: 500
    lineHeight: 1.1
    letterSpacing: "-0.02em"
    fontFeature: "tnum"
  mono:
    fontFamily: "Geist Mono, ui-monospace, SF Mono, Consolas, monospace"
    fontSize: "0.92rem"
    fontWeight: 500
    letterSpacing: "0.01em"
    fontFeature: "tnum"
rounded:
  hairline: "6px"
  inner: "8px"
  control: "10px"
  tile: "12px"
  metric: "14px"
  panel: "16px"
  window: "20px"
  pill: "999px"
spacing:
  xs: "6px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "22px"
  gutter: "20px"
  section: "clamp(80px, 11vw, 150px)"
components:
  button-primary:
    backgroundColor: "{colors.accent-blue}"
    textColor: "{colors.light-surface}"
    rounded: "{rounded.control}"
    padding: "0 14px"
    height: "36px"
  button-primary-hover:
    backgroundColor: "{colors.accent-blue-deep}"
  button-secondary:
    backgroundColor: "{colors.light-surface}"
    textColor: "{colors.light-ink}"
    rounded: "{rounded.control}"
    padding: "0 14px"
    height: "36px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.light-ink-2}"
    rounded: "{rounded.control}"
    padding: "0 14px"
    height: "36px"
  button-story:
    backgroundColor: "{colors.story-navy}"
    textColor: "{colors.light-surface}"
    rounded: "{rounded.tile}"
    padding: "0 20px"
    height: "48px"
  button-story-hover:
    backgroundColor: "{colors.accent-blue-deep}"
  search-hero:
    backgroundColor: "{colors.light-surface}"
    textColor: "{colors.story-navy}"
    typography: "{typography.mono}"
    rounded: "{rounded.panel}"
    padding: "0 8px 0 20px"
    height: "64px"
  search-bar:
    backgroundColor: "{colors.dim-surface}"
    textColor: "{colors.dim-ink}"
    typography: "{typography.mono}"
    rounded: "{rounded.tile}"
    padding: "0 6px 0 12px"
    height: "42px"
  pick-chip:
    backgroundColor: "{colors.light-surface}"
    textColor: "{colors.story-navy}"
    rounded: "{rounded.pill}"
    padding: "8px 14px"
  card:
    backgroundColor: "{colors.dim-surface}"
    textColor: "{colors.dim-ink}"
    rounded: "{rounded.panel}"
    padding: "20px 22px"
  tag:
    backgroundColor: "{colors.dim-surface-2}"
    textColor: "{colors.dim-ink-2}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "0 9px"
    height: "24px"
  link-button:
    backgroundColor: "{colors.accent-wash-light}"
    textColor: "{colors.accent-blue-deep}"
    rounded: "{rounded.pill}"
    padding: "6px 10px"
  tab:
    backgroundColor: "transparent"
    textColor: "{colors.dim-ink-3}"
    padding: "0 14px"
    height: "46px"
  tab-selected:
    textColor: "{colors.dim-ink}"
  product-window:
    backgroundColor: "{colors.window-navy}"
    textColor: "{colors.dim-ink}"
    rounded: "{rounded.window}"
---

# Design System: Stock Analysis Engine

## Overview

**Creative North Star: "Many Futures, One Instrument"**

The system has two worlds that share one type family, one accent and one shape grammar. The **story world** (Home, How it works, Evidence) is always bright: a cool-white ground, deep navy ink, and the data-series colours used as light. A canvas fan of simulated price paths spreads out of the hero search field over a slow, blurred glow of the same hues, and dark navy product windows float on the page holding the real report components. The **working world** (Report, Compare, the trace drawer, the command palette) is a calm instrument. It opens in Dim, with Light and Dark selectable. Each theme has its own surfaces and ink steps rather than inverted values.

Density follows the job. Story pages breathe, with section padding up to 150px, display headlines at -0.04em tracking and prose capped between 46 and 66 characters. Working pages are compact and tabular: 16px grid gaps, figure tiles separated by 1px hairlines, and Geist Mono figures that can each be clicked to open their trace. Motion follows a single rule. Everything uses an exponential ease-out, and content is already in its final state at rest; animations only play in from an offset.

The build rejects the fintech split hero (phone mockup, logo strip, equal feature cards). It has no uppercase labels, no eyebrow text above headings and no glyph icons. Icons are Phosphor SVG throughout.

**Key Characteristics:**
- Two worlds: the bright story world and the themed working world (Dim by default).
- One blue accent. Status colours carry meaning only and always come with an icon and a label.
- Geist for words, Geist Mono with tabular numerals for figures, tickers and ticker inputs.
- Soft, navy-tinted ambient shadows. Hover lifts by 1 to 2px.
- Story sections end on slanted edges. Dark product windows sit on the bright pages.
- Exponential ease-out motion that never hides content at rest.

## Colors

The palette is cool and blue-anchored. Navy and slate neutrals carry almost everything, one accent blue does the pointing, and three data-series hues work as both chart ink and story light.

### Primary
- **Signal Blue** (accent-blue): the one accent on light surfaces. Used for primary buttons, focus rings, the selected tab ink, active progress dots, meters and the caret. Because it is also series-1, the accent and the first data series are the same colour on purpose.
- **Deep Signal Blue** (accent-blue-deep): hover state for every blue and navy control, plus text links and figure call-to-action text on light grounds.
- **Lit Signal Blue** (accent-blue-lit): the accent in Dim, Dark and the product windows. It is the brighter step needed to hold contrast on slate and navy. Lit Signal Blue Strong (accent-blue-lit-strong) is the hover and link step in Dim and Dark.
- **Blue Wash** (accent-wash-light): background for selected palette items, link buttons and the verdict result cell. Dark themes use a translucent version of the lit blue instead.

### Secondary
- **Series Orange** (series-orange; series-orange-dim on dark): the second data series. It marks the bear scenario, the second company in Compare and the right side of the butterfly chart.
- **Series Green** (series-green; series-green-dim on dark): the third data series. It marks the bull scenario.

### Tertiary
- **Story Glow** (glow-blue, glow-aqua, glow-peach): blurred radial light behind the story hero and page heads (blur 70 to 80px, opacity 0.45 to 0.68). These are lighter versions of the series hues and appear only as light, never as fills or text.
- **Fan Percentile Ink** (fan-high for the 90th percentile line, story-navy for the median, fan-low for the 10th percentile line): these are the hero fan's labelled lines, darkened from the series hues so their labels are readable on white.

### Neutral
- **Story Ground** (story-ground) and **Story Navy** (story-navy, with navy-2 for body text and navy-3 for captions): the bright world's paper and ink. Story rules are navy at 10% alpha.
- **Window Navy** (window-navy, window-surface, window-surface-2, window-line): the scoped dark palette inside product windows on story pages.
- **Dim Slate** (dim-page through dim-line-strong): the default working theme. It is a slate step between Light and Dark.
- **Light Paper** (light-page through light-line-strong): the working Light theme. Pages sit on cool grey with white cards on top.
- **Dark Graphite** (dark-page through dark-line): the working Dark theme. It goes deep without reaching pure black.
- **Semantic status** (up, down and warn, each with a light and a dim step; status-good, status-warning, status-critical and status-neutral for dots and meters). Every status colour has a matching soft tint used as its badge background.

### Named Rules
**The One Accent Rule.** Blue is the only accent. Orange and green appear only as data series. Up, down and warn appear only as status, and only alongside an icon and a text label.

**The Two Worlds Rule.** Story pages are always bright, whatever the app theme is set to. Working pages follow the theme. When working components appear inside a story page, they render within a dark product window using the scoped window palette.

**The Unrated Rule.** A company with no rating never takes a series colour. Its bands are drawn with a hatched line-strong pattern and its markers in ink-3.

## Typography

**Display Font:** Geist (with system-ui, -apple-system, Segoe UI)
**Body Font:** Geist
**Label/Mono Font:** Geist Mono (with ui-monospace, SF Mono, Consolas)

**Character:** The pairing is a single grotesque family. It is set heavy and tight in the story world and medium and even in the working world, with its monospace sibling used for anything you could compute with. All weights are self-hosted through @fontsource: Geist 400 to 700 and Geist Mono 400 to 600.

### Hierarchy
- **Display** (700, clamp(2.4rem, 4.4vw, 4.1rem), 1.03, -0.04em): story hero and page-head h1s, plus the closing call. Story Navy, balanced wrap.
- **Headline** (700, clamp(1.9rem, 3.6vw, 3rem), 1.06, -0.035em): story section headings.
- **Headline Step** (700, clamp(1.5rem, 2.4vw, 2rem), 1.12, -0.03em): scrollytelling steps and Evidence sections.
- **Title** (600, clamp(1.45rem, 2.4vw, 1.9rem), 1.2, -0.025em): the working-world page h1 (company name). Card titles drop to 600 at 1rem.
- **Body** (400, 15px, 1.55): working-world text. Story prose is set at 1.02 to 1.06rem with 1.6 to 1.7 line height, capped at 46 to 66ch. The bottom-line summary uses 1.06rem with 1.7 line height and an 82ch cap.
- **Label** (400 to 500, 0.74 to 0.82rem, sentence case): KPI labels, table heads, legends and captions. All in ink-3.
- **Figures** (Geist Mono 500, tabular): hero price at clamp(1.9rem, 3.4vw, 2.6rem) and -0.03em, KPI values at 1.55rem and -0.02em, drawer figure at 2.1rem, metric values at 1.5rem.

### Named Rules
**The Mono Means Number Rule.** Geist Mono with tabular numerals is used for figures, tickers, ticker inputs, counts, kbd hints and formulas. It is never used for prose. Placeholders inside mono inputs switch back to Geist.

**The Two Weights of Voice Rule.** Story headings are 700 with -0.03 to -0.04em tracking. Working headings stop at 600 with no more than -0.025em. A working page never uses the display ramp.

**The Sentence Case Rule.** No uppercase labels and no eyebrows. Labels are small, sentence case and set in ink-3.

## Layout

Story pages use full-bleed sections with content held to 1200px and side padding of clamp(20px, 5vw, 48px). Sections are spaced by clamp(80px, 11vw, 150px). The hero is at least max(720px, min(100svh, 920px)) tall. Its copy column is 640px wide and indented by clamp(20px, 6vw, 96px), and the fan canvas fills the hero behind it. The explanation and How it works sections pair a sticky column with a scrolling one (0.8fr / 1.2fr and 1.2fr / 0.8fr). Evidence uses a 200px sticky table of contents beside a 780px reading column. Below 900px, every split collapses to a single column. The sticky window gives way to inline scene copies, and the table of contents is hidden.

The working world sits in a 1240px shell with 20px gutters under a sticky, blurred app bar (82% page colour, backdrop blur 14px). The tabs bar is sticky too and blurs at 12px. Content follows a 16px grid gap. The KPI strip is a five-column hairline grid that reflows to 6-column spans at 1000px and 2 columns at 620px. Two-column card grids collapse at 920px, and stacked tables turn into labelled rows at 640px.

Spacing is roughly an 8px rhythm with half steps (6, 8, 12, 16, 22). Card padding is 20 by 22px and tile padding is 14 to 16px.

## Elevation & Depth

Surfaces stay close to flat. Depth comes from tonal layering (page, surface, surface-2, surface-3) and from soft ambient shadows, tinted navy on light grounds and black on dark ones. Elevation responds to state: picks, metrics and chips rise 1 to 2px and move to the larger shadow on hover. Larger shadows are reserved for objects that really float: the hero search, product windows, the drawer and the command palette. Overlays use a 50% ink scrim with a 3px blur.

### Shadow Vocabulary
- **Rest** (`0 1px 2px rgba(16, 24, 40, 0.06)`; on Dim, `0 1px 2px rgba(0,0,0,0.25)`): cards, KPI strip, secondary controls.
- **Raised** (`0 1px 2px rgba(16,24,40,0.05), 0 6px 20px -8px rgba(16,24,40,0.10)`; on Dim, `0 1px 2px rgba(0,0,0,0.2), 0 10px 28px -12px rgba(0,0,0,0.5)`): hover lift and tooltips.
- **Hero search** (`0 1px 2px rgba(11,27,51,0.06), 0 24px 48px -24px rgba(11,27,51,0.30)`): the story search field.
- **Window** (`0 2px 4px rgba(11,27,51,0.08), 0 40px 80px -36px rgba(11,27,51,0.55)`): dark product windows on bright pages.
- **Focus halo** (`0 0 0 4px` accent wash, or 5px on the hero search): focus-within on fields, layered under the 2px accent outline.

### Named Rules
**The Ambient Only Rule.** Every shadow is soft, blurred and offset only on the y axis, with a negative spread. There are no hard offset shadows and no coloured glows on controls.

## Shapes

Corners are gently rounded on a fixed ladder. Panels and cards use 16px, controls and fields use 10px (the app search bar uses 12px), tiles use 12 to 14px, product windows use 20px, and chips, tags, stances, switches and link buttons are fully rounded. Inner elements inside a segmented control take 8px. Small marks such as kbd and inline code take 6px. Meters and bars are rounded to half their height. Story sections close on a slant: the hero's bottom edge cuts 72px diagonally (32px below 900px), and the closing section's top edge mirrors it. Borders are 1px hairlines everywhere. KPI and stat grids are drawn as 1px gaps over the line colour, not as borders.

### Named Rules
**The Slant Rule.** A slanted clip-path edge appears only where a story section begins or ends. Working surfaces stay rectilinear.

## Components

### Buttons
- **Shape:** gently rounded (10px), 36px tall. Icon buttons are 36px square.
- **Primary:** Signal Blue fill with white text, a 1px inner top highlight and the rest shadow. Hover moves to the deep step.
- **Secondary / Ghost:** Secondary is a surface fill with a line-strong border. Ghost is transparent with ink-2 text and a surface-2 fill on hover.
- **Press:** translateY(1px) scale(0.985) over 110ms. Disabled buttons drop to 50% opacity.
- **Story CTA:** a navy fill (48px tall, 12px corners, weight 600) whose hover turns to the deep accent and nudges its arrow 3px right. The nav uses the same navy as a full pill.
- **Link button:** a Blue Wash pill with deep blue 0.8rem text. Used for "show how" actions.

### Chips
- **Showcase pick chip (story):** a pill of white at 78% with a navy-rule border, a mono ticker at 600 and a short description in navy-3. Hover gives an accent border, full white, a 2px lift and a soft navy shadow.
- **Tag (working):** a 24px pill on surface-2 with a hairline border. The mono variant is used for exchange and ticker. The live variant uses up-soft and up ink.
- **Stance badge:** a 32px pill at weight 600 in a status tint (good, warn, bad or neutral), always with an icon.
- **Method chip (trace):** "on" uses accent wash and deep blue. "Off" uses surface-2 and ink-3 with a strikethrough.

### Cards / Containers
- **Corner Style:** 16px panels. Metric tiles 14px, verdict nodes 12px.
- **Background:** surface on page, with surface-2 for nested notes, formulas and reads.
- **Shadow Strategy:** rest shadow at rest. Clickable tiles lift to raised (see Elevation & Depth).
- **Border:** 1px line. The bottom-line card mixes 22% accent into the border and adds a top accent-wash gradient.
- **Internal Padding:** 20px by 22px for cards, 16 to 18px for KPI and metric tiles.

### Inputs / Fields
- **Style:** surface fill, 1px line-strong border, mono text with Geist placeholders. The hero search is 64px with 16px corners. The app search bar is 42px with 12px corners. Compare slots are 42px with 10px corners.
- **Focus:** the border turns accent and a 4px accent-wash halo appears (5px on the hero). The caret is accent everywhere.
- **Error:** inline text below the field. Error cards mix 35% critical into the border and show a down-soft icon tile.

### Navigation
- **Story nav:** absolute over the hero. Brand on the left, page links on the right in navy-2 at 0.92rem and weight 500, darkening to navy on hover or when active. The end is a navy pill CTA and a translucent white search pill showing a kbd hint. Below 640px, secondary links and the CTA are hidden.
- **App bar:** sticky and blurred. Brand mark is a 30px accent tile with 9px corners. The search bar is centred and a theme segmented control sits on the right. Below 900px, search moves to its own row.
- **Tabs:** 46px, ink-3 text that turns to ink when selected. A single 2px accent ink line slides under the active tab (transform, 420ms expo). Mono count pills.
- **Segmented control:** 3px padding, 11px track on surface-2. The selected state is a surface pill that slides between options using clip-path.

### Trace Drawer (signature)
A right-side dialog (up to 520px) on the page colour. The clicked figure flies from its spot in the report into the drawer head. The trace below is a numbered vertical chain: 28px mono dots joined by a 2px connector that draws downward as each step lands. Pass steps take up-soft dots, the deciding step takes a solid accent dot with a wash halo, and the result step sits in a bordered surface tile. Formulas are mono on surface-2.

### Product Window (signature)
A 20px-radius window with a 46px title bar, using the scoped window-navy palette. It sits on story pages with the window shadow and holds real report components and scenes, not mockups.

### Range Fan (signature)
The story hero canvas: simulated paths fanning out from the search field, a soft blue band between the 10th and 90th percentiles, and three labelled lines (90th, median, 10th). The ends are masked so they fade out. Hovering a showcase chip reshapes the fan to that company's volatility.

## Do's and Don'ts

### Do:
- **Do** set every figure, ticker and ticker input in Geist Mono with tabular numerals, and keep prose in Geist.
- **Do** keep blue as the single accent, and pair every status colour with an icon and a text label.
- **Do** keep story pages bright whatever the app theme, and render working components inside story pages through a dark product window.
- **Do** use the radius ladder: 16px panels, 10px controls, full pills for chips, tags, stances and switches, and 20px for product windows.
- **Do** animate with `cubic-bezier(0.16, 1, 0.3, 1)` on transform, opacity and clip-path only, and keep content in its final state at rest so reduced motion loses nothing.
- **Do** show hover by lifting 1 to 2px with an accent border and the raised shadow. Show press with a 0.97 to 0.985 scale.

### Don't:
- **Don't** use orange or green as accents or decoration. They are data series only.
- **Don't** give an unrated company a series colour. Use the hatched line-strong band and ink-3 marker.
- **Don't** put uppercase labels or eyebrow text above headings. Labels are sentence case in ink-3.
- **Don't** use hard offset shadows or coloured glows on controls. Shadows are ambient, offset on y only.
- **Don't** use the 700 display ramp or slanted edges on working surfaces.
- **Don't** use pure black for the Dark theme. Its page is the graphite step, not #000.
