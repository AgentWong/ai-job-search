# Writing Style Guide

Reference for AI agents generating resumes and cover letters. The goal is to produce content that reads like **you** actually wrote it, not like an AI generated it.

---

## Why This Matters

Recruiters are increasingly flagging AI-generated resumes. Posts on LinkedIn from hiring managers describe receiving stacks of resumes that all sound identical -- the same inflated verbs, the same generic phrasing, the same cadence. These resumes get skimmed or discarded because they signal that the applicant put minimal effort into the application.

A writing style guide solves this by teaching the AI how **you** naturally communicate. The result is content that passes the "did a human write this?" test because it's grounded in your actual writing patterns, not generic AI defaults.

**To make this work, you need to provide real samples of your writing.** The guide below is a template with placeholder examples. Replace them with excerpts from your own writing -- Reddit comments, Slack messages, blog posts, emails to coworkers, forum replies, anything where you're explaining technical work in your natural voice. The more samples you provide, the better the AI can mimic your style.

### How to Collect Writing Samples

1. Search your Reddit/forum post history for comments where you describe technical work
2. Check old Slack messages or emails where you explained a project or troubleshot an issue
3. Look at any blog posts, documentation, or READMEs you've written
4. Even informal messages count -- how you naturally explain things to a coworker is exactly the voice you want

Save your raw samples in a separate reference file (e.g., `.ai_references/writing_style.md`) and use this guide to document the patterns you observe.

---

## Core Voice Characteristics

<!-- CUSTOMIZE: Replace the example quotes below with excerpts from YOUR writing. The "Natural" examples should be direct quotes from your posts, messages, or documents. The "AI-sounding" examples show what generic AI output looks like for contrast. -->

### 1. Direct and Blunt

State things plainly without hedging or softening. Don't dress up bad situations or oversell good ones.

**Natural (your voice):** "My last role was basically sysadmin work with a DevOps title. I didn't touch CI/CD for the first two years."
**AI-sounding:** "My previous role provided diverse exposure to cloud infrastructure beyond traditional DevOps boundaries."

### 2. Honest About Limitations

Openly admit what you don't know or haven't done. This paradoxically builds credibility.

**Natural (your voice):** "To be honest, it was a basic Python script -- maybe 150 lines. Nothing fancy."
**AI-sounding:** "Leveraged Python scripting capabilities to automate browser-based workflows."

### 3. Concrete Over Abstract

Always use specific details, numbers, tool names, and real examples rather than vague claims.

**Natural (your voice):** "You push a button in the CI pipeline and 45 minutes later you've got a fully configured web portal with HTTPS."
**AI-sounding:** "Developed comprehensive automation solutions that streamlined deployment processes."

### 4. Problem-Solver Framing

Describe work in terms of real problems and practical fixes, not responsibilities or duties.

**Natural (your voice):** "The VPN kept dropping, so I enabled logging via Terraform and traced it to an IKE negotiation mismatch."
**AI-sounding:** "Responsible for troubleshooting and maintaining VPN connectivity across multi-cloud environments."

### 5. Varied Sentence Structure

Mix short punchy statements with longer technical explanations. Not every sentence follows the same pattern.

**Natural (your voice):** "I come from the ops side." followed by a detailed technical paragraph.
**AI-sounding:** Every sentence is 15-25 words, starting with an action verb, following the same cadence.

---

## Words and Phrases to AVOID (AI Tells)

These words and patterns are commonly flagged by AI detection tools and rarely appear in natural technical writing:

### Overused AI Verbs
- "Leveraged" / "Leveraging"
- "Spearheaded"
- "Streamlined" (use "cut," "reduced," "simplified" instead)
- "Orchestrated" (unless literally referring to container orchestration)
- "Facilitated"
- "Championed"
- "Cultivated"
- "Synergized"

### Generic AI Filler
- "Cutting-edge technologies"
- "Cross-functional collaboration"
- "Proven track record of delivering high-quality solutions"
- "Passionate about..."
- "Excited to contribute..."
- "Results-driven" (as a standalone descriptor)
- "Dynamic environment"
- "Stakeholder engagement"
- "Transformative impact"

### AI Sentence Starters (Cover Letters)
- "I am thrilled to..."
- "I am eager to bring my expertise..."
- "With a strong foundation in..."
- "I am confident that my skills..."

---

## Words and Phrases to USE

<!-- CUSTOMIZE: Replace these with verbs and patterns from YOUR writing samples. How do you naturally describe building something? Fixing something? Improving something? -->

### How You Describe Work
- "Wrote" / "Built" / "Set up" / "Put together"
- "Figured out" (for troubleshooting)
- "Got it working" / "Made it work"
- "Replaced X with Y" (direct substitution framing)
- "Eliminated" / "Cut" (for reductions)

### How You Frame Achievements
- Lead with the **problem or situation**, then the **action**, then the **outcome**
- Use parenthetical asides for technical context: "(using CI pipelines to run Terraform + Ansible)"
- Include specific numbers: "153 hours to under 5 hours," "less than 200 lines"
- Reference what **didn't work** before your solution

### Sentence Patterns You Use
<!-- CUSTOMIZE: What patterns do you naturally fall into? Short declarations? Numbered lists? Hedging phrases? Contrast framing? Pull examples from your writing samples. -->
- Short declarative: "I come from the ops side of IT."
- Numbered alternatives: "it's either 1) find a remote job, 2) bag groceries, or 3) move"
- Honest qualification: "To be honest," "I can't honestly say"
- Contrast framing: "It's not like I don't understand the issue."

---

## Application to Resume Bullets

### Resume Bullet Formula

**Pattern:** [What was broken/slow/missing] → [What you built/fixed] → [Measurable result]

<!-- CUSTOMIZE: Replace these examples with bullets derived from YOUR cv_full.md content. -->

**Good (sounds like a person):**
- "Replaced 100+ separate API calls with a single query, which eliminated the rate limiting that kept blocking our drift detection."
- "Built Ansible roles for HA clusters that cut deployment from 150 hours of manual work to under 5 hours, all through the CI pipeline."
- "Wrote PowerShell scripts using runspaces to scan 600+ machines in parallel -- reduced audit prep from days to hours."

**Bad (sounds like AI):**
- "Leveraged advanced cloud-native solutions to streamline infrastructure deployment processes, resulting in significant efficiency gains."
- "Spearheaded the development of comprehensive automation frameworks that transformed operational workflows."
- "Orchestrated cross-functional collaboration to deliver high-quality infrastructure solutions aligned with organizational objectives."

### Key Differences

| Natural Style | AI Style |
|---------------|----------|
| Names the specific tool | Says "comprehensive solution" |
| States the exact number | Says "significant improvement" |
| Explains what was wrong before | Starts with what they did |
| Uses plain verbs (built, wrote, set up) | Uses inflated verbs (leveraged, spearheaded) |
| One clear idea per bullet | Crams multiple vague claims into one bullet |
| Includes technical specifics in parentheses | Stays at a high level |

---

## Application to Cover Letters

### Opening Paragraph

State who you are, what you do, and why this role fits. No fluff.

<!-- CUSTOMIZE: Write an example opening in YOUR voice. -->

**Good:** "I'm a Cloud Engineer with 7+ years in IT, mostly focused on Terraform, Ansible, and AWS. Your posting lines up with what I've been doing, so I wanted to walk through the specifics."

**Bad:** "I am thrilled to submit my application for the Cloud Engineer position at your esteemed organization. With a passion for cutting-edge cloud technologies and a proven track record of delivering transformative infrastructure solutions, I am confident I would be an exceptional addition to your dynamic team."

### Requirement Matching

Write like you're explaining what you did to a coworker, not writing a press release.

**Good:** "You need someone with Terraform and multi-cloud experience. I built the Terraform configs for an AWS-to-Azure site-to-site VPN -- dual tunnels with BGP routing. Took what was a 3-week manual process down to 2 days."

**Bad:** "I have extensive experience leveraging Terraform to architect sophisticated multi-cloud connectivity solutions, seamlessly bridging AWS and Azure environments through automated infrastructure provisioning."

### Closing Paragraph

Keep it short. Don't grovel.

**Good:** "Happy to go into more detail on any of this. Thanks for your time."

**Bad:** "I am profoundly grateful for your consideration and am deeply enthusiastic about the opportunity to contribute my extensive expertise to your organization's continued success."

---

## Usage Instructions for AI Agents

When generating resume or cover letter content:

1. **Read this guide first** before drafting any content
2. **Check every sentence** against the "Words to AVOID" list
3. **Use the bullet formula:** Problem → Action → Result, with specific tools and numbers
4. **Vary sentence length** -- mix short and long, don't make every bullet the same structure
5. **Use plain verbs** -- built, wrote, set up, fixed, replaced, cut, eliminated
6. **Include technical specifics** -- name the actual tools, services, and quantities
7. **Frame as problem-solving** -- what was broken, what you did, what improved
8. **Keep it honest** -- if something was small-scale, don't inflate it
9. **Read the final draft aloud** -- if it sounds like a LinkedIn influencer, rewrite it
