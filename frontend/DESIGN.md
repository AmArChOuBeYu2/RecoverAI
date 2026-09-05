# NIVARAN — Design System Specification

**Tagline**: *Revenue recovery, resolved intelligently.*

---

## 1. Vision & Purpose

Nivaran is built for financial intelligence, risk control, and automated revenue recovery.
The visual identity reflects **precision, analytical clarity, financial credibility, and policy authority**.

It avoids generic consumer SaaS aesthetics (excessive rounded cards, loud purple AI gradients, decorative blobs, neon backgrounds) in favor of a **high-density, editorial-meets-operating-system aesthetic**.

---

## 2. Color Palette & Semantics

### Primary Color Tokens
* **Foundation Dark**: `#0B0F17` (Deep Obsidian Charcoal — workspace background)
* **Surface Container**: `#0F172A` / `#1E293B` (Dark Slate — structured cards and data tables)
* **Primary Accent**: `#10B981` (Emerald Teal — verified revenue, recovery success, action CTA)
* **Secondary Accent**: `#6366F1` (Indigo — AI reasoning, segmentation taxonomy)
* **Border System**: `#1E293B` (Subtle 1px rules and structural dividers)

### Data Provenance & State Colors
Every state in Nivaran has strict visual semantics. Colors MUST NOT be mixed.

| State | Color Token | Hex / Class | Description |
| :--- | :--- | :--- | :--- |
| **VERIFIED** | Emerald Green | `#10B981` / `bg-emerald-950 text-emerald-300 border-emerald-500/40` | Authoritative Razorpay confirmed outcome |
| **OBSERVED** | Cyan Teal | `#06B6D4` / `bg-cyan-950 text-cyan-300 border-cyan-500/40` | Historical empirical observation |
| **SIMULATED** | Violet Purple | `#8B5CF6` / `bg-purple-950 text-purple-300 border-purple-500/40` | Synthetic test/counterfactual scenario |
| **PROJECTED** | Amber Gold | `#F59E0B` / `bg-amber-950 text-amber-300 border-amber-500/40` | Policy simulation statistical estimate |
| **BLOCKED / RISK** | Crimson Red | `#EF4444` / `bg-red-950 text-red-300 border-red-500/40` | Policy or TrustGate prevented action |
| **PENDING** | Slate Gray | `#64748B` / `bg-slate-900 text-slate-400 border-slate-700` | Action executed, outcome awaiting verification |
| **HUMAN REVIEW** | Orange | `#F97316` / `bg-orange-950 text-orange-300 border-orange-500/40` | Escalated for manual intervention |

---

## 3. Typography Hierarchy

Nivaran uses a dual font pairing to balance financial authority with analytical readability.

1. **Display & Editorial Metrics**: *Instrument Serif*
   - Used for hero headlines, key numerical values, and executive metric totals.
   - Characterized by crisp serif geometry and high editorial contrast.

2. **Functional UI & Data Tables**: *Plus Jakarta Sans*
   - Used for navigation, body copy, operational tables, badges, and controls.
   - Clean, geometric sans-serif ensuring high legibility at dense data scales.

3. **Technical Identifiers**: *JetBrains Mono / System Monospace*
   - Used selectively for UUIDs, transaction IDs, status codes, and API parameters.

---

## 4. Layout & Surface Principles

* **Density**: High data density with explicit 1px borders (`border-slate-800`).
* **Corner Radius**: Selective radius (`rounded-lg` or `rounded-xl`), avoiding over-rounded bubble cards.
* **Separation**: Information is separated by structural rules, subtle background tints, and asymmetric grid placement rather than floating cards on white backgrounds.
* **Badges**: Every numerical metric or table row explicitly carries a Provenance Badge so the user immediately knows whether a number is `VERIFIED`, `OBSERVED`, `SIMULATED`, or `PROJECTED`.

---

## 5. Motion Guidelines

* **Orchestration**: Entrance transitions use single-pass opacity fades (`duration-300`).
* **Interactive Elements**: Hover states feature subtle border glow transitions (`hover:border-emerald-500/40`).
* **Guided Demo**: Progress indicator transitions reflect real async API execution.
* **Restraint**: No scroll-triggered parallax, bouncing animations, or floating decorative blobs.
