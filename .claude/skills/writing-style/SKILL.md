---
name: writing-style
description: Apply Alex's writing voice and AI-tell bans whenever generating recruiter-facing or career-related text — resumes, cover letters, LinkedIn posts/messages/comments, recruiter follow-up emails, application essays, "About Me" / bio sections, interview thank-you notes, or any prose that will be read by a hiring manager, recruiter, or professional contact. Enforces hard bans (em dashes, "Happy to ..." phrasing, AI-tell verbs like leveraged/spearheaded/streamlined/thrilled) and the problem→action→result bullet pattern. Use before drafting, and re-check before returning content.
---

# Writing Style (Digest)

Read this before drafting any recruiter-facing or career-related prose. For the full guide with voice examples, see [config/profile/writing_style_guide.md](../../../config/profile/writing_style_guide.md) — that file is the canonical source; this skill is the always-on enforcement layer.

## Hard bans (non-negotiable)

These produce immediate rewrites. The agent's own examples in `config/profile/writing_style_guide.md` are not exempt — if a quoted example violates a rule, don't propagate it.

- **No em dashes (—). Ever.** Replace with a comma, period, colon, or parentheses. Zero exceptions.
- **No hyphens as clause separators.** "Built X - cut time by half" is banned. Use a period, comma, or restructure. Hyphens are fine inside hyphenated words (`site-to-site`, `day-to-day`) and as list bullets.
- **No "Happy to ..." phrasing.** Recognized LLM tell. Replace with direct alternatives: "If you want to talk through this, I'm available." / "Let me know if you want to get on a call."
- **No AI-tell verbs:** leveraged, leveraging, spearheaded, streamlined, streamlining, facilitated, facilitating, orchestrated (unless about container orchestration), championed, cultivated, synergized.
- **No generic AI filler:** cutting-edge, cross-functional collaboration, proven track record, passionate about, results-driven, dynamic environment/team, stakeholder engagement, transformative impact, comprehensive suite, drive operational excellence, esteemed organization.
- **No AI cover-letter openers:** "I am thrilled to ...", "I am eager to bring my expertise ...", "With a strong foundation in ...", "I am confident that my skills ..."

## Voice rules

- **Plain verbs:** built, wrote, set up, fixed, replaced, cut, eliminated, figured out, got it working.
- **Be specific:** name the tool, service, and number. "Cut deployment from 153 hours to under 5" beats "significant time savings". "107 separate API calls" beats "many API calls".
- **Problem → Action → Result** for bullets: what was broken/slow/missing, what you built/fixed, the measurable outcome.
- **Honest about scope.** If something was small, don't inflate it. "A simple (less than 200 lines) script" is fine — owning the scope reads as credible, not as weak.
- **Vary sentence structure.** Mix short declaratives with longer technical explanations. Don't follow the same cadence in every bullet.
- **Tenure references** (cover letters, bios): round fractional years DOWN in 0.5 increments. Nimbus Technologies May 2022 – Jan 2026 = 3 years 8 months → "3.5 years", never "4 years".

## Quick-check before returning content

Before handing back any drafted text, scan it for:

1. Any `—` character (em dash). Search and delete every one.
2. The literal string "Happy to" (case-insensitive). If present, rewrite the sentence.
3. The banned verbs and filler phrases above. If any appear, rewrite.
4. Bullets that don't follow problem → action → result. If a bullet has no problem context or no measurable result, ask whether it earns its space.

For resumes and cover letters specifically, the `scripts/validate_resume_content.py` and `scripts/validate_cover_letter_content.py` scripts enforce most of these rules as hard exit-code gates. Run them when generating those artifacts.

## When NOT to apply

This skill is for prose Alex would put his name on. Don't apply to:

- Internal config / YAML / CSV content (it's not prose).
- Code comments and commit messages (different conventions).
- Verbatim quotes from job postings, employer-supplied text, or third-party content.
- Technical documentation drafts where formal tone is genuinely appropriate.
