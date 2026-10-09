# Frontend implementation plan (4 days)

Audience: the professor, in a live demo the developer drives. Inspiration: Stripe's websites (luminous gradients, product windows, orchestrated motion), translated into this project's own world, never copied.

## 1. Direction

**Two worlds, one palette.**

| | Story surfaces | App surfaces |
|---|---|---|
| Pages | Start screen, How it works, Evidence | Report, Compare, traces |
| Mode | Persuade / Read | Operate |
| Ground | Bright, near-white, slanted gradient bands | Dim by default (Light / Dark selectable) |
| Feel | Stripe-style storytelling: animated gradient, dark "product windows" floating on light, big confident type | Linear-calm working screen; the polish shows in motion and detail |

**Signature idea: the gradient is the data palette.** The animated hero gradient is drawn from the chart series colours (blue `#3987e5`, orange `#d95926`, aqua `#199e70`, plus deep navy ink). The same colours the visitor later reads in the charts first appear as the light of the start screen, so the story world and the data world are visibly one system.

**Type:** Geist for UI and display (600 to 700 weight, tight tracking at large sizes), Geist Mono for every number.

**Motion grammar (one library, used everywhere):** `motion` (Framer Motion) for:
- shared-element morphs (a number flies into its explanation);
- staggered reveals;
- scroll-linked scenes;
- animated presence.

Charts draw in by path length. Numbers tween when they change. The View Transitions API handles route changes. Everything has a reduced-motion static equivalent, and expensive effects pause off screen.

## 2. The four memorable moments

1. **Watch a verdict get built.** Click any headline figure:
   - The number morphs into the header of a side panel.
   - The chain animates step by step: data, then classification, then methods, then weights, then blend, then range, then verdict. The connector line draws, values count up, and the deciding rule lights up.
   - Every trace is deep-linkable (`?explain=fairvalue`), so the browser Back button closes it.
2. **Simulated futures in 3D:**
   - On the start screen, an illustrative Monte Carlo cone sits in a dark product window, with time scrubbing, volatility control and drag-to-rotate.
   - In the report, the same cone is driven by the company's real one-year volatility, overlaid with the engine's fair-value band. It is labelled "illustrative, not a forecast".
3. **How it works.** A sticky, scroll-driven story:
   - One real showcase company flows through the engine's stages, with live numbers from its snapshot.
   - The diagram on the left transforms per step, and the text on the right explains it.
4. **Compare.** Two companies side by side. Value, quality and confidence bars animate between them, and swapping a company re-tweens everything.

## 3. Information architecture

| Route | Surface |
|---|---|
| `/` | Start: gradient hero, search, showcase picks, futures window, three proof tiles linking to How it works / Evidence / Compare |
| `/s/:ticker` | Report (current tabs), with `?tab=` and `?explain=` in the URL |
| `/compare?a=TCS&b=INFY` | Compare |
| `/how-it-works` | Methodology story |
| `/evidence` | Validation results from `/validation` |
| Ctrl+K (any page) | Command palette: jump to a ticker, a report section, an "Explain ..." trace, a page, or a theme |

## 4. Architecture

- **Routing:** `react-router` v7 (library mode). The report state lives in the URL so the demo can jump anywhere and Back works.
- **Data:** a `useAnalysis(ticker)` hook:
  1. It checks the demo manifest first; snapshots open instantly from `public/demo/<TICKER>.json`.
  2. Otherwise it starts a live job and polls, with an in-memory cache.
  3. A badge shows "Snapshot, 9 Oct 2026" or "Live".
- **Snapshot export:** a new `scripts/export_demo.py` runs the engine for 8 showcase tickers and writes the serialized results plus a manifest (date, engine version). Candidates: TCS, HDFCBANK, ATHERENERG, TATASTEEL, BAJFINANCE, WAAREEENER, INFY, ITC.
- **Gradient:** a small raw-WebGL fragment-shader component (no three.js). It shows a static frame under reduced motion, pauses off screen, and falls back to CSS gradients.
- **3D:** stays lazy-loaded (three.js only loads on the pages that need it).
- **Code layout:**
  - `pages/` (Start, Report, Compare, HowItWorks, Evidence)
  - `components/` (existing)
  - `motion/` (shared variants, `useTween`, `CountUp`)
  - `lib/demo.ts`
- **New dependencies:**
  - `react-router`
  - `motion`
  - `cmdk`, for the command palette (accessible and small)

## 5. Schedule

Each day ends with a commit and a click-through of the demo script.

### Day 1: foundation and the hero moment (highest value)
1. Stabilise the uncommitted interactive work:
   - Build it and check it in the browser on desktop and mobile in all three themes.
   - Fix what breaks and commit.
2. Add the router and pages scaffold, `motion`, and the URL state for tab and explain.
3. Add demo mode: write the export script, run it for the showcase set, then add the loader hook and the snapshot badge.
4. Build "Watch a verdict get built":
   - the shared-element morph;
   - staggered trace steps with count-up values;
   - the connector line drawing in;
   - deep links.
5. Add motion to the report:
   - KPI count-ups on load;
   - chart draw-in;
   - tab and explorer transitions with a sliding indicator.

### Day 2: the Stripe-bright start screen
1. Build the WebGL data-palette gradient hero with slanted section edges.
2. Put the search in the hero itself. The showcase picks open instantly from snapshots.
3. Move the futures cone into a dark product window:
   - it reveals on scroll;
   - its sliders and readout are polished.
4. Build the real-data futures cone in the report's Valuation tab:
   - inputs are realized volatility and the fair-value band;
   - it carries an "illustrative" label.
5. Add proof tiles linking to How it works, Evidence and Compare.

### Day 3: the story pages
1. **How it works:** six to seven pinned scroll scenes using one snapshot's real numbers:
   - data;
   - routing;
   - methods;
   - blend;
   - range;
   - confidence;
   - verdict.
2. **Evidence:** real `/validation` data:
   - the ML-versus-baseline chart (and why it is hidden);
   - news-tagging precision and recall;
   - the peer-method comparison;
   - consensus comparison;
   - the golden set.
   It uses honest captions, including the failures.

### Day 4: compare, palette, polish, rehearsal
1. Build Compare, side by side with animated bars. It uses snapshots for instant swaps.
2. Build the Ctrl+K command palette.
3. Accessibility and reduced-motion pass. Performance check on the demo laptop (target: 60 fps gradient, cone under 16 ms per frame, and the WebGL fallback verified).
4. Run the design detector, a final screenshot round, and an independent finish review.
5. Rehearse the demo script twice and fix only demo blockers.

**Cut order if behind:**
1. Compare shrinks to a fixed TCS-versus-INFY view.
2. How it works drops to four scenes.
3. The real-data cone in the report is dropped. The start-screen cone stays.

The verdict-building moment and demo mode are never cut.

## 6. Demo script (about 6 minutes)
1. **Start screen.** The gradient and futures cone: "a stock has no single future". Scrub time and raise volatility.
2. **Search TCS.** It opens instantly from the snapshot. Walk through the bottom line and the verdict path.
3. **Click Fair value.** Watch it get built. Click Stance and watch the rules decide.
4. **Valuation tab.** Show the method rows, the sensitivity cell readout and the real-data cone.
5. **Ctrl+K, then "ATHERENERG".** A loss-making company gets NOT RATED; the trace shows which gate stopped it.
6. **Compare** TCS against ATHERENERG.
7. **How it works.** Scroll the story.
8. **Evidence.** "Our ML model failed its test, so we hide it." End there.
9. **Optional:** analyse an unseen ticker live to prove it is real (start it during step 6).

## 7. Done means
- Every headline figure opens its trace, and every trace is reachable by URL.
- The showcase companies open in under 300 ms. Live analysis still works and is labelled.
- No page stalls or breaks with WebGL disabled or reduced motion on.
- Mobile layout holds at 390 px, although the demo itself is on desktop.
- The detector is clean, the finish review is done, and the work is committed locally (not pushed).
