# aegish Blog Post Outline

## TL;DR (3-4 bullet points)

- What aegish is (one sentence)
- Why is it relevant?
- Headline result: 4/9 models meet all targets; smaller models beat flagships
- Honest caveat: structural bypasses exist (exit, interactive shells, encoding). This is still a prototype

## 1. Introduction: Why Monitor Commands with an LLM?

- Block before execution: AI flags catastrophic actions before they run, not after
- Simple to configure: no need for complex authorization models or fine-grained permissioning
- Cheap, deep investigation: when suspicious activity is detected, cheap AI labor removes the human bottleneck of investigating context and code
- Attackers can't safely iterate: even if an attack could succeed, the attacker risks being caught on the very first attempt -- the high-stakes environment favors the defender
- Thesis: "What if we asked an LLM to understand what a command means before running it?"

## 2. Related Work: What Exists and Where aegish Differs

- Emerging but fragmented space: a few tools share individual properties, none combine all six
- Directly comparable tools:
  - baish: LLM-based script analysis (batch/pipe, not interactive shell; dormant PoC)
  - SecureShell: LLM-based command gating (targets AI agents, not human users; library, not shell)
  - Touch et al. (CRiSIS 2024): fine-tuned RoBERTa for 5-level risk classification (academic, requires training data)
- Adjacent tools (same problem, no LLM):
  - Rule-based agent guards (Destructive Command Guard)
  - Traditional ML classification (SLP/CAMLIS 2021, XGBoost, F1=0.874)
  - Restricted shells, PAM command filtering, static analysis
- Defense-in-depth layer diagram (aegish at Layer 6: semantic/intent)
- Comparison matrix: aegish vs baish vs SecureShell vs AppArmor/SELinux vs rbash vs EDR vs Security Copilot vs CyberArk
- The six-property differentiator table (pre-execution, semantic, zero-shot, NL explanations, no kernel access, systematic benchmarking)
- Position explicitly: not replacing kernel-level enforcement, adding a semantic layer on top
- Key gap aegish fills: interactive shell + zero-shot LLM + enforcement -- no existing tool does all three

## 3. How It Works

- One-paragraph description: LLM-powered shell that intercepts every command, classifies as ALLOW/WARN/BLOCK
- The 13-rule decision tree (summarized as a table: Rule -> Pattern -> Action)
- Walk through 2-3 example commands showing the JSON output
- Plot of the categories

## 4. The Benchmark

- Dataset: 1,172 commands (676 malicious GTFOBins + 496 harmless)
- GTFOBins curation: 8 categories, placeholder normalization (137 commands affected -- replacing "evil"/"malware" with realistic paths)
- Harmless curation: HuggingFace source + LLM-generated, aggressive filtering
- Scoring: Asymmetric (BLOCK=correct for malicious; ALLOW or WARN=correct for harmless). Explain why (attacker can type "y" to bypass WARN)

## 5. Results

- Ranking table and tier breakdown (Tier 1/2/3)
- Three success criteria: Detection >=95%, Pass >=90%, aegish Score >=0.85
- The surprising finding: smaller models win (GPT-5-mini > GPT-5.1; Haiku > Opus > Sonnet)
- Root cause 1: content filter activations (Anthropic Sonnet and Opus only, 50 errors arguably correct)
- Root cause 2: WARN-hedging in larger models
- Per-category difficulty ranking (reverse-shell=100% -> command=57.20%)
- Plots: ranking_table.png, detection_vs_pass.png, category_heatmap.png

## 6. Production Viability: Cost & Latency

- Cost comparison: GPT-5-mini at $33.60/month vs Opus at $386.70/month
- Gemini Flash latency dissection: 70.9s headline but 76.7% is rate-limit queuing; actual server time 6.8s
- Production recommendation: GPT-5-mini primary + Haiku fallback
- Plots: cost_vs_score.png, latency_distribution.png

## 7. Limitations

- Framed as "red-teaming our own work"
- Structural bypasses:
  - exit drops to unmonitored parent shell (zero-skill, 100% success)
  - Interactive program escapes (vim :!bash, less !bash, python, ssh)
  - BASH_ENV injection (experimentally confirmed)
  - Pre-expansion vs post-expansion gap (variable substitution)
- Prompt injection -- commands go directly into LLM prompt without sanitization
- Fail-open design -- all providers fail -> WARN -> user can proceed
- Benchmark gaps: harmless set saturated (96.8-100%), "command" category undersampled
- Inherent LLM limitations: non-determinism, latency, cost
- The 6 quick wins that would address the worst issues

## 8. Conclusion & Future Work

- A new defense-in-depth layer, not a silver bullet
- Quick wins: fail-closed, sanitize BASH_ENV, block interactive shell-spawners
- Roadmap: semantic caching, offline mode, CIS compliance, audit trails
- Open questions: adversarial robustness, context awareness, determinism

## Appendix A: Full System Prompt

- Complete ~180-line prompt verbatim

## Appendix B: Error Distribution by Model

- Full error breakdown table (ALLOW/WARN/CONTENT_FILTER/FORMAT_ERROR per model)

## Appendix C: All Plots

- All 7 plots with brief captions

## Appendix D: Hardest Individual Commands

- All commands that fooled more than 5 models
