---
name: scientific-analysis
description: >
  Structured workflow for analyzing datasets or experiments: frame the
  question, check data quality, choose the right statistics, and report with
  uncertainty. Use for any data analysis, benchmark comparison, or research
  question. Adapted from K-Dense-AI/claude-scientific-skills.
---

# Scientific Analysis

Work through these phases in order. State explicitly when you skip one.

## Phase 1 — Frame
- Restate the question as a testable claim with a measurable outcome.
- Name the unit of analysis, the population it generalizes to, and what would
  falsify the claim.

## Phase 2 — Data quality
Before any statistic: missingness per column, duplicates, range/units checks,
and whether n is sufficient for the intended test (rule of thumb: ≥5 per cell
for chi-square, ≥30 per group for stable means).

## Phase 3 — Method selection
- Comparing 2 groups → t-test (normal) or Mann-Whitney U (otherwise).
- 3+ groups → ANOVA / Kruskal-Wallis, then post-hoc with correction.
- Associations → Pearson/Spearman; never call correlation causation.
- Proportions → chi-square or Fisher exact if any cell < 5.
State assumptions and how you checked them.

## Phase 4 — Report
- Lead with the effect size and its confidence interval, not the p-value.
- Report exact p-values (p = 0.03, not "significant"); "n.s." for ≥ 0.05.
- One short "Limitations" section: sample, measurement, multiplicity.
- If asked for a chart: plot raw data with summary overlay, never summary alone.
