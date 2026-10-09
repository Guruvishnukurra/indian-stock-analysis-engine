# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **Primary audience (evaluation):** the developer's professor, watching a live demo the developer drives on a laptop or projector. The job is to judge an academic project: is the engine rigorous, honest and well engineered, and is the interface a credible, impressive piece of work?
- **Operator during the demo:** the developer, who needs instant, reliable navigation between showcase companies and explanations while talking.
- Not built to sell to investors or to give investment advice.

## Product Purpose

An explainable stock-analysis engine for Indian listed companies (NSE/BSE). For any ticker it produces a fair-value **range** from several valuation methods, separate Quality / Valuation / Timing verdicts, a confidence score, market-implied expectations, bear/base/bull scenarios, AI-tagged news events and a plain-language bottom line. Success: every number on screen can be traced back to the method, inputs and period that produced it.

## Positioning

It never gives a single price target or a prediction. It shows ranges, states how far to trust them, routes each business type to the methods that fit it, refuses verdicts when the methods do not fit (NOT RATED), and hides its own ML model because walk-forward validation showed it does not beat baselines. Explainability and honest validation are the product, not decoration.

## Operating Context

- Live academic presentation; four days of build time from 2026-10-09.
- Backend: FastAPI (`src/api/main.py`) with job polling; a full analysis takes 30 s to 3 min, so a **demo mode** of pre-computed showcase analyses (labelled as snapshots with their date) opens instantly, with live analysis for any other ticker.
- Evidence endpoint `/validation` serves the real validation results.

## Capabilities and Constraints

- Frontend: React 19 + TypeScript + Vite; custom SVG charts; three.js / React Three Fiber available for 3D.
- Themes: the working report defaults to a Dim theme (Light and Dark selectable). Story surfaces (start screen, methodology, evidence) may use their own bright world.
- Requested surfaces: start screen, report, "how we got here" traces, methodology walkthrough, compare two stocks, command palette (Ctrl+K), validation evidence page.
- Data quirks: Yahoo Finance data, about 4 years of statements, no point-in-time history.

## Brand Commitments

- Name in use: "Stock Analysis Engine".
- The user asked for the look and feel of Stripe's websites as inspiration (luminous gradients, polished motion, product storytelling), without copying Stripe's brand.
- Copy rules already in force: ₹ for rupees, no em dashes, disclaimer always visible ("Analytical assessment for research and education. Not investment advice...").

## Evidence on Hand

- Real engine outputs for any NSE ticker (live), and showcase snapshots once exported.
- Validation results (docs/README.md, `/validation`): ML trend 36.0% balanced accuracy vs 33.3% baseline (fails the 5 pp gate, hidden); peer-selection evaluation; news-event tagging precision 86% / recall 55% on 120 held-out headlines; fair value vs analyst consensus on 48 NIFTY 50 companies; golden set of 32 stocks.
- No testimonials, users, accuracy claims or returns exist; none may be invented.

## Product Principles

1. Ranges over points: never present a value as a prediction or target.
2. Every number is traceable: one click from any figure to how it was reached.
3. Show the evidence, including what failed.
4. Simulations and snapshots are labelled as what they are.
5. The demo must never stall: instant paths for showcase companies.

## Accessibility & Inclusion

Keyboard operable throughout; status never conveyed by colour alone; reduced-motion users get static equivalents of every animation.
