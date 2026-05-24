# Task 2 — Lifting 3% Free→Paid Conversion on a Family-Office Intelligence SaaS

**Brief:** "A SaaS platform focused on providing Family Office Intelligence to a targeted audience is only converting 3% of free accounts to paying users. The SaaS platform founders want to increase MRR. To that end, how would you improve this free trial to paid conversion rate?"

The same "How We Work" framework that governs Task 1 applies here. I will not jump straight to recommendations; I will start by interrogating the 3% number itself, because the framing of the problem changes the recommendations entirely.

---

## 1. Question the signal — what is "3%" actually measuring?

**Observed:** 3% of free accounts convert to paying users.

**Assumed (by anyone proposing fixes on this number alone):** that 3% is below where it should be, that the bottleneck is somewhere in the funnel, and that experiments aimed at the free→paid transition will move it.

**What I would verify before committing resources:**

1. **What is the denominator?** Free-account signups via cold paid marketing convert very differently from free-account signups via outbound sales, partner referrals, or ICP-matched waitlists. A 3% conversion on cold paid marketing is mid-pack for B2B PLG. A 3% conversion on ICP-matched outbound is catastrophic. **Until the denominator is decomposed, "3%" is not actually a metric — it's a weighted average of unrelated funnels.**

2. **What is the comparable benchmark?** Self-serve PLG SaaS in the 2–5% range is normal (OpenView's 2024 PLG report); developer-tools SaaS sometimes runs 6–10%; vertical-B2B with very narrow ICP can run anywhere from 1% (broad funnel) to 15% (curated funnel). Family-office intelligence is *unusually narrow* — the target buyer is a UHNW family office (~10–15k worldwide), or perhaps the analysts who work for them. The relevant benchmark is not "B2B SaaS conversion"; it is "vertical SaaS with a known-buyer-list."

3. **What stage of revenue?** A 3% conversion at $50/month MRR is a different business from 3% at $5,000/month MRR. The latter may be perfectly healthy; the former is not. The brief is silent on ACV.

4. **What is the time-to-conversion?** "Free→paid" might mean trial-end conversion at 14 days, or it might mean a 12-month average. If users convert at month 9, the "3%" reported today is reading historical cohorts at low maturity.

**Could be wrong because:** the founders may have already done this decomposition and the 3% they reported is the cohort-clean, denominator-clean number. If so, the recommendations below still apply — they would just be sharper.

**Decision before proposing fixes:** I would not commit to free→paid optimisation work without a basic cohort decomposition. The first 2 hours of any engagement here are spent on the decomposition, not on the optimisation.

---

## 2. Hypotheses, each with a falsification condition

I'll enumerate the most likely root causes, with explicit "what would prove this wrong" framing. The visible-thinking discipline requires that every hypothesis be testable.

### H1: Free signups are weakly ICP-fit

**Hypothesis:** A meaningful share of the free signups are not family offices, not FO analysts, and not anyone who can or would buy this product. The 3% is dragged down by tyre-kickers.

**Falsified by:** Self-reported "I work at a family office" rate at signup is >70%, AND verifiable signals (work email domain, LinkedIn lookup of signup name) confirm that rate at the same level.

**Test:** Add a one-question signup gate ("Are you part of a family office? [SFO / MFO / Adviser / Other]") and compare conversion rates by self-reported category over 4 weeks. If the "Other" bucket dominates and converts at <0.5%, the funnel is being polluted by non-ICP signups.

**If true:** Tighten the free funnel — require LinkedIn login or work-email validation, raise the friction on signup. Sounds counter-intuitive (more friction → higher conversion) but works when the bottleneck is *who* signs up, not how many.

### H2: Free tier provides no aha-moment

**Hypothesis:** The free tier shows a generic dashboard or a thin sample — neither of which lets the user discover a specific, valuable insight that they did not have before. The user signs up, browses for 90 seconds, and leaves. There is no activation event that crystallises the product's value.

**Falsified by:** A defined activation event exists in the data (e.g., "first FO query that returned a result the user starred"), AND users who hit that event convert at >15%, AND >40% of free signups hit that event within 7 days.

**Test:** Define the activation event hypothetically, instrument it, and segment cohorts. If activation rate is <20% AND activation-correlation with conversion is weak, the product is not delivering value in the free experience — no amount of pricing or paywall optimisation will help until that is fixed.

**If true:** Activation experiments dominate. Add guided "first-query" tours that surface one high-value insight per user (e.g., "Here are 3 FOs that recently invested in your category"). Pre-load a curated demo cohort. Surface "you discovered X" moments.

### H3: Paywall in the wrong place / wrong feature

**Hypothesis:** The free tier has enough utility that users get their work done within it; they don't need to upgrade. Or alternatively, the paywall locks the wrong feature — one that users don't viscerally want — while the genuinely valuable feature is available free.

**Falsified by:** Survey or in-product behaviour shows that paid-tier-locked features are the ones users reach for AND fail to use. If they reach for paid features at all, activation isn't the bottleneck; if they don't reach for them, the paywall is gating something users don't yet want.

**Test:** Track "feature-hit-paywall" events. If <10% of free users ever hit a paywall in 14 days, the paywall is in the wrong place. If 60% hit it but bounce, the feature isn't yet "must-have" — either the value of the locked feature is unclear, or the user hasn't reached the workflow where they need it.

**If true:** Audit the paywall placement. The classic FO-intelligence locked features are: full-record export, deep-history (e.g., last 5 years of 13F changes), alerting/notifications, multi-user collaboration. One of these should be the *exact* thing a serious user can't do their job without. If the locked feature is "advanced filters," that's a vitamin, not a painkiller.

### H4: Weak follow-up / no sales-assist

**Hypothesis:** Free signups in this vertical (FO intelligence) are buying signals worth $5k–$50k ACV. At those ACVs, pure self-serve conversion is uncommon — the buyer wants to talk to a human before committing. If there's no nurture sequence, no in-app outbound, and no sales-assist for high-intent free users, those users just stall.

**Falsified by:** Sales-touched cohort converts at the same rate as untouched, AND ACV is genuinely small enough ($50–500/month) that self-serve is the right model.

**Test:** For the next 100 free signups that hit defined intent thresholds (3+ logins, 5+ queries, 1+ saved record), trigger a personalised email or in-app outreach. Compare 14-day conversion against a control cohort. If the touched cohort converts at 2–3× the rate, the missing piece is sales-assist, not product.

**If true:** Add a lightweight sales-assist layer. For a small team, this is not "hire a sales rep" — it's "one founder spends 30 min/day responding to high-intent users." That alone can move 3% to 8% on a low-volume but high-ACV funnel.

### H5: Pricing is wrong

**Hypothesis:** Pricing is too high (sticker shock), too low (signals "this isn't serious"), or shaped wrong (per-seat when buyers want per-record).

**Falsified by:** Win/loss analysis shows pricing is not the named objection in >30% of churn or no-conversion cases.

**Test:** Annotate every "did not convert" in CRM with a reason code; for the next 50 conversations include a pricing-specific question. If <20% cite pricing, it's not the issue.

**If true:** Pricing changes. But this hypothesis is **deliberately last** in my ordering. Pricing changes are the highest-friction lever to pull — they affect existing customers, downstream commitments, and require a public announcement. They should be tested only after the activation and trigger hypotheses (H2, H3, H4) have been ruled out. Pricing is rarely the actual bottleneck in a 3% funnel.

---

## 3. Recommendation: experiment ordering

The hypotheses above are independently testable. But they are not equally cheap to test, and they don't have equal expected lift. My ordering for a 4-week sprint:

**Week 1: Decompose the 3%.** Cohort the existing data by signup source, self-reported ICP, ACV-equivalent tier, time-to-convert. *Cost: low (data work). Expected output: a sharper version of the problem.*

**Week 1–2: Define and instrument the activation event.** Run H2's test. Activation experiments are the highest-leverage and lowest-risk first move. If the activation rate is poor, no other lever matters yet. *Cost: low (instrumentation + analysis). Expected lift if true: 3× to 5×.*

**Week 2–3: Add a one-question ICP gate to the signup flow, A/B-tested.** Tests H1. If accepted, expect free-signup volume to drop and free-paid conversion rate to rise — net MRR effect depends on the relative magnitudes. *Cost: low (frontend change). Expected lift on conversion rate: 1.5× to 3×; expected lift on MRR: smaller because volume drops.*

**Week 3–4: Add high-intent in-app outreach.** Tests H4. *Cost: medium (need an in-app messaging tool and 30 min/day of founder time). Expected lift on conversion rate: 2× to 3× on the touched cohort, ~1.5× blended.*

**Week 4–6: Audit paywall placement based on activation data.** Tests H3. *Cost: low (analysis) + medium (paywall reposition). Expected lift: depends entirely on what the activation analysis reveals.*

**Week 6+: Only after the above, consider pricing changes.** Tests H5. *Cost: high (existing-customer comms, pricing-page work, GTM messaging). Expected lift: highly variable.*

---

## 4. Expected outcomes — uncertainty visible

If the 4-week sprint runs to plan and the data behaves "averagely":
- **Best case:** 3% → 8–10% blended conversion, driven primarily by H2 (activation) and H4 (sales-assist). Substantial MRR lift assuming volume doesn't drop.
- **Median case:** 3% → 5–6%. The ICP gate cuts volume; the activation work delivers a partial lift; sales-assist captures the high-intent tail.
- **Worst case:** 3% → 3.5%. The funnel isn't the bottleneck — the *product* doesn't provide enough unique value to convert users at any volume. This is a fundamental product-market-fit signal, not a conversion-optimisation problem. The right response is not more A/B tests; it is a customer-development cycle.

**What I am uncertain about:**
- The relative weight of H1 vs H2. In a vertical-B2B SaaS, weak ICP fit is often the proximate cause AND a symptom of weak activation. Both can be true.
- The realistic ACV. The brief doesn't say. If ACV is $50/month, the sales-assist hypothesis (H4) has limited unit economics. If ACV is $5,000/month, it dominates.
- Whether the "3%" excludes self-serve trials that became annual contracts post-sales-call. If those are counted separately, the actual self-serve conversion rate may be even lower; if they're included, the rate is healthier than it looks.

---

## 5. What I would do differently from a typical answer

Most candidates given this prompt will propose:
- "Improve onboarding"
- "Add a free trial"
- "Lower pricing"
- "More aggressive email nurture"

These are not wrong, but they are *unranked*. The honest answer in a "How We Work" frame is: **I do not know what to fix until I know what the 3% is composed of**. The first response is not a fix; it is a question. The second is a falsifiable hypothesis. The third is the cheapest, most-leveraged test.

I would write the founders a one-page note that says: "Before we touch the product, give us 90 minutes with the cohort-level data. We can write a test plan that lifts MRR ≥30% over 6 weeks at low engineering cost — but the order of the tests matters, and the order depends on the data."

That note is what hires for the role described in the "How We Work" doc.

---

**Author:** Rukhtam Amin
**Submission date:** 2026-05-25
