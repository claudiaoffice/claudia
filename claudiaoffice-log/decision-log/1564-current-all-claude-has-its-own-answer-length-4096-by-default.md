---
id: D1564
title: "Claude has its own answer length, 4096 tokens by default"
status: current
applies-to: all
date: 2026-11-24
round: "E7.2 Skills and persona per app, with CODE-80 to CODE-82 (branch e7-2-skills-and-persona)"
supersedes: []
superseded-by: []
---

# D1564 · Claude has its own answer length, 4096 tokens by default

**Decided 2026-11-23** (the owner, answer to Q8 of the E7.2 grilling).

`AiSettings.max_tokens` (512) was one number for every provider and is the number Claude's runner got. 512 tokens is right
for the 7B local model, which is slow, and wrong for Claude: a story of 300 words is about 450 tokens and the block of
requests comes on top of it, so "write a sentence" worked and "300 words" did not (CODE-82).

Now `ClaudeSettings.max_tokens` is Claude's own answer length, 4096 by default; the local model's stays 512
(`AiSettings.max_tokens`, `--ai-max-tokens`). An older `settings.json` without it reads as 4096. `PUT /api/admin/settings/ai`
takes `claude.max_tokens` (at least 1, else 400 "the answer length must be at least 1"). The AI page shows one field "Max
answer length (tokens)" and, in it, the value of the provider that is chosen (mock `ai-provider-5`).

**Not capped by the server.** Anthropic refuses a value above the model's limit; the administrator's test question on Apply
then shows the reason. **Costs.** A longer answer may take longer and costs more tokens; the timeout (`timeout`, 180 s) is
unchanged and still ends an answer that takes too long.
