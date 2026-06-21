# Linear Adoption Recon — Remixa

**Date:** 2026-06-21 · **Plan:** Linear **Business** (fn8 workspace) · **Author:** Claude (recon)
**Method:** two parallel multi-agent recon sweeps (broad capability map + feedback-loop deep-dive, web-sourced & cited) + an authed peek at the live `fn8` workspace. Knowledge verified against Linear's 2025–2026 changelog/docs, not training priors.

> **One-line takeaway:** Most of what fn8 needs is *already unlocked* by the Business license and just not adopted. The single highest-leverage move retires code we shipped today (the commit→Linear join) in favour of Linear's **native GitHub integration**; the real Business payoff is the **agent platform** (Code Intelligence + Agent Automations, free-in-beta) which compounds with fn8's existing MCP/OAuth wiring.

---

## 0. Live `fn8` workspace state (authed, 2026-06-21)

| Thing | State | Implication |
|---|---|---|
| GitHub integration | **Enabled** | Native commit/PR↔issue + status automation is one config away — not an install. |
| Codex, Cursor integrations | **Enabled** | Agent connectors already present. |
| Linear MCP endpoint (fn8 config) | **`https://mcp.linear.app/mcp`** (`.claude.json:1292`) | Already on the current endpoint — the "migrate off deprecated `/sse`" task is **done**. |
| Available integration connectors | Slack, Linear Asks for Slack, Intercom, GitHub Copilot, Sentry/Seer, + MCP connectors for Cursor / ChatGPT / Claude / v0 / Windsurf | Broad surface; Customer-Requests intake channels available. |
| Enabled feature surfaces (settings nav) | AI & Agents, Agent personalization, Initiatives, Customer requests, Pulse, Asks, Releases, Documents, SLAs, Code & reviews | The new/Business capability is largely **live and un-adopted**, not unpurchased. |

---

## 1. What's genuinely new since fn8 last looked (verified)

- **Linear Agent → named public beta (Mar 24, 2026)** on the "Linear for Agents" platform (shipped May 2025). Third-party agents are first-class **@mentionable / assignable** workspace members via `actor=app` + `app:assignable`/`app:mentionable` scopes, and **do not consume billable seats**. This is the *inbound* counterpart to fn8's outbound-only MCP. _(linear.app/developers/agents, changelog 2026-03-24)_
- **Coding Sessions (Jun 11, 2026):** Linear's first-party agent writes code via **Claude Code + OpenAI Codex** — issue → reviewed diff, in-app. Same Claude Code engine Stefan already uses. _(changelog 2026-06-11)_
- **Code Intelligence (May 14, 2026, Business, free-in-beta):** gives the agent **indexed read access** to the connected repo, so it reasons over the actual FastAPI/Next.js code, not just issue text. _(changelog 2026-05-14)_
- **Linear MCP `/sse` deprecated → `https://mcp.linear.app/mcp`**; tool surface expanded Feb 5, 2026 (initiatives, project/initiative updates, milestones, project labels, attachments, load-by-URL). _(changelog 2026-02-05)_ — **fn8 already on the new endpoint.**
- **`attachmentCreate` is URL-idempotent** (re-posting the same URL updates rather than duplicates) and renders GitHub-style cards — a strictly better primitive than `commentCreate` for any commit/PR→issue link. _(linear.app/developers/attachments)_
- **Linear Diffs / native code review (May 2026)** + **Releases (Apr 30, 2026)** — issue status can reflect **actual prod deploys** (Fly.io/Vercel), not merge state.
- **Triage Intelligence** (renamed from Product Intelligence; auto-apply Sep 19, 2025) and **OAuth Application Manifests** (Jun 18, 2026, infra-as-code OAuth config).

---

## 2. Prioritized adoption shortlist

| # | Capability | Effort | Impact | Supersedes | First step |
|---|---|---|---|---|---|
| 1 | **Native GitHub integration** (commit/branch/PR link + PR-state→issue-status automation) | S | **High** | the **entire PR #11** commit→comment join (`linear-commit-join.yml` + `scripts/linear_commit_join.py`) and its dedup/attribution limits | GitHub is already Enabled — in `fn8` Settings → Integrations → GitHub, confirm **remixa** is connected, map `PR open→In Progress` / `merge→Done` to fn8's states, then **delete the script**. |
| 2 | **Migrate Linear MCP `/sse` → `mcp.linear.app/mcp`** | — | — | — | **Already done** (`.claude.json:1292`). Just note the expanded write tools (initiatives, milestones, `create_attachment`) are now usable from Claude Code. |
| 3 | **Code Intelligence + Agent Automations + Triage Intelligence** (Business, **free-in-beta**) | S | **High** | manual FN8-N grooming | Connect the **remixa** repo for code access; enable Code Intelligence in AI Settings; add one Triage Automation that runs an fn8 Skill (e.g. DoR/DoD or auto-label). Evaluate while free. **Watch-item:** GA may move to usage pricing. |
| 4 | **Evaluate Coding Sessions** (first-party `@Linear` agent: Claude Code + Codex) | M | High | — | Assign one low-risk FN8-N bug to `@Linear`; review the diff; track AI-credit burn. Forces the explicit **build-vs-buy** decision (delegate to `@Linear` vs host bob/claude on the agent platform with the FN8 ledger). Likely hybrid. |
| 5 | **Convert the existing `fn8` OAuth app → a true Agent** (`app:assignable`/`app:mentionable`, inbound webhook) | M/L | High | the one-way poster | Upgrade fn8 from outbound MCP poster to a **bidirectional agent**: bob/claude/codex become @mentionable/assignable delegates on FN8-N issues; thought/action/response/error activities map onto fn8's narration discipline; the elicitation→awaitingInput loop gives a native Rule-19 human-gate. |

**The honest callout:** PR #11 (merged today) is what move #1 retires. It wasn't wasted — it got observability live immediately and forced the now-reusable `LINEAR_API_KEY` + `Linear-API-Remixa` vault item into place — but the **durable path is native GitHub integration**. If you ever want a *custom* link instead, use `attachmentCreate` (URL-idempotent, card-rendering) rather than `commentCreate`.

---

## 3. The big later-phase play: user feedback → product development

### How the loop works in Linear
Capture feedback as a **`CustomerNeed`** ("request") attached to an **issue** (optionally a customer) → group issues into **projects** → rank by **request COUNT** → build the most-requested → on issue completion, Linear notifies the internal subscriber and reopens the source thread; a human sends the "we shipped it." Requests have **no independent lifecycle** — they inherit the attached issue's state, so "close the loop" is mechanically just moving that issue to **Done**. **Business already covers every channel Remixa needs — no Enterprise upgrade.**

### ⚠ Load-bearing mismatch (architect around this)
Linear's **`Customer` is an organization keyed on email domain** (B2B/account-shaped, with revenue/tier/size attributes for ARR-weighted prioritization). **Remixa's users are thousands of low-ARPU individual consumers on personal Gmail/iCloud — they do NOT map to customer orgs.** Consequences:
- **Do NOT create a Customer per user.** `customerUpsert` matches **by domain only** (externalId is merged into a domain-matched record, *not* a match key) — so upsert would mint a new Customer on every call.
- **The only prioritization signal that works for a consumer base is request COUNT / demand volume** ("1,000 creators want pitch-shift"). Revenue/tier/ARR weighting is B2B and would sit empty — don't architect around it. (You *could* push a coarse free-vs-Pro "tier" from Stripe to weight paying creators, but count is the engine.)

### Best intake channels for Remixa (ranked)
1. **PRIMARY — GraphQL API (`customerNeedCreate`) from Remixa's FastAPI**, `customerExternalId = Clerk user id`. The only channel that fits a self-serve, anonymous, high-volume consumer base. All plans.
2. **EARLIEST/MANUAL — Discord/Slack community of first creators**; a human turns each message into issue+request (`Ctrl/Cmd+R`). Doesn't scale past dozens; ideal for the first alpha cohort.
3. **BRIDGE — Email intake** (`feedback@remixa` / in-app "email us") forwarding into a Linear Triage queue. Gives a real **reply-back path** (synced thread) that pure API ingest lacks.
4. **OPTIONAL BUY (scale) — third-party in-app widget + public voting roadmap** (Featurebase / Userback / Productlane). **Linear has NO native in-app widget or public voting roadmap** — buy only if you want a public "vote on features" flywheel.
5. **DEFER — Intercom/Zendesk/Front** (Business+, needs a staffed support tool); **NOT a fit:** Salesforce/Gong (Enterprise B2B), Linear Asks (internal-ops, not consumer feedback).

### API blueprint (the path Remixa would build)
- **Surface:** a Next.js "suggest / report" panel POSTs `{display_name, text, route/screen context, optional deeplink}` to a FastAPI route `POST /feedback` on Fly.io. **Bind `clerk_user_id` server-side from the Clerk session — never trust it from the client body.**
- **Backend:** raw GraphQL over `httpx` (there is **no official Python SDK** — only `@linear/sdk` for TS; hand-write 3–4 versioned mutation constants → `https://api.linear.app/graphql`).
  1. **Customer dedup (make-or-break):** keep an app-side map table in Remixa's Postgres `clerk_user_id → linear_customer_id`. First-ever feedback → `customerCreate(name, externalIds=[clerk_user_id])`, store the returned id. Subsequent → look up the map, skip create. **Do not rely on `customerUpsert`** (domain-only matching).
  2. **Issue anchor:** route feedback through a **Triage** issue (create a new Triage issue, or reuse a rolling "Inbound feedback" issue) to obtain `issueId` (every official `customerNeedCreate` example is issue-anchored; `projectId` is tagged `[INTERNAL]`).
  3. **Attach:** `customerNeedCreate(issueId, body=text, customerExternalId=clerk_user_id, attachmentUrl=deeplink)`.
  4. **Two app-side dedup layers** (Linear dedups neither): customer-dedup (the map table) + request-dedup (guard against double-submit). **Issue-level** dedup ("same feature asked 100×") = early: human-merge in Triage so COUNT accumulates on one issue; later: Triage Intelligence auto-applies team/labels/project + flags duplicates.
- **Auth/infra:** single workspace **personal API key as a Fly.io secret**; header `Authorization: <key>` (**no "Bearer"** for personal keys). Rate limits (5,000 req/hr, 3M complexity pts/hr) are non-binding at one-mutation-per-feedback; add a simple queue + backoff for growth. **No-ops at pre-alpha** (zero users = zero calls; switches on without re-architecture).
- **Close-the-loop (later):** subscribe to a customer-request/issue-update **webhook** *(payload shape UNVERIFIED)* or poll the linked issue's state; on `Done`, notify the originating Clerk user in-app. **Linear does NOT auto-message external end users** — Remixa must build this notify-back itself.

### Phased plan (gated by Remixa's growth)
- **Phase 1 — Structure & data-model (now, zero real users) · effort S.** Create a dedicated Remixa **Triage team** + project taxonomy ("Sound generation quality", "Remix export", "Creator monetization"). Confirm Customer Requests is enabled and `customerNeedCreate` works on Business with a `write`-scoped key (the one plan-gate to confirm). Design (don't populate) the `clerk_user_id → linear_customer_id` map; define the `/feedback` contract; write the dormant mutation constants. **Draft the GDPR position** (legal basis, data-minimization — what feedback fields leave the EU to Linear — and a **DPA with Linear** before any real user data flows; loop in the CLO role).
- **Phase 2 — First alpha users, manual capture · effort S.** Community channel (Discord/Slack) and/or `feedback@remixa` → Linear Triage. Hand-convert meaningful messages into issue+request (`Ctrl/Cmd+R`); human-merge duplicates so COUNT accumulates. For paying creators only, optionally a lightweight Customer with a coarse Stripe tier. Reply to shipped requests by hand (personal touch is an asset at this scale).
- **Phase 3 — In-app intake (scale switch-on) · effort M.** Ship the Next.js feedback surface → `POST /feedback` → `customerNeedCreate` per the blueprint. Turn on the app-side dedup map + request guard. Lean on Triage Intelligence to auto-groom inbound.
- **Phase 4 — Demand-driven roadmap + close-the-loop · effort M.** Rank projects/issues by **request count**; tie larger bets to **Initiatives**; use **Insights** for themes/volume; build the webhook/poll → in-app "the thing you asked for is live" notify-back. Optionally add a public voting roadmap (buy) if a community flywheel is wanted.

### Risks / watch-items
- **GDPR / EU AI Act:** Remixa is EU; feedback flows to Linear (US) — needs a **DPA + data-minimization + CLO sign-off** before real user data flows.
- **No native in-app widget or public voting** — build on `customerNeedCreate` or buy a third-party widget.
- **Close-the-loop notify-back to anonymous users is not automatic** — Remixa must build it.
- **`important` flag is binary (0/1)** — ranking must come from request *count*, not per-request priority.
- Code Intelligence / Agent Automations are **free-in-beta** — **GA pricing may become usage-based**.

---

## 4. Gaps to verify (before building)
- ✅ **VERIFIED (2026-06-21):** `customerNeedCreate(input:{issueId, body})` succeeds with the Full-access `Linear-API-Remixa` key (raw `Authorization` header, no Bearer). Customer Requests **is enabled** in the `fn8` Business workspace and the key carries the scope. Smoke: created a throwaway issue (`FN8-706`) → attached a need → deleted the issue. **Phase 3 (in-app feedback → FastAPI → Linear API) is feasible as designed.**
- **Customer-request/issue webhook payload shape** for close-the-loop (marked UNVERIFIED by the sweep).
- Whether the remixa **repo** (not just the workspace) is connected to the GitHub integration, and which status-automation rules already exist.
- AI-credit consumption model for Coding Sessions (to inform build-vs-buy).

---

## 5. Recommended first actions (this week)
1. **Configure native GitHub status automation** for remixa, then delete `linear_commit_join.yml` + `scripts/linear_commit_join.py` (move #1).
2. **Enable Code Intelligence on the remixa repo** + one Triage Automation (move #3) — free, compounds immediately.
3. **Run the `customerNeedCreate` smoke** with the `Linear-API-Remixa` key to unblock the Phase-3 design (gap #1).
4. Decide **build-vs-buy** on the agent side: evaluate `@Linear` Coding Sessions on one FN8-N bug vs standing up the `fn8` OAuth app as a first-class Agent (moves #4/#5).

---

## 6. Execution status — "execute them all" (2026-06-21)

Honest reduction after attempting to execute the shortlist:

**Done / already in place**
- ✅ **Phase-1 structure** — the **Remixa project** exists: `https://linear.app/fn8/project/remixa-b8aa90632d22`. (Area taxonomy = a 1-minute label/project add when feedback starts; not built ahead of need.)
- ✅ **MCP endpoint** already current (#2).
- ✅ **`Linear-API-Remixa` key** + **`customerNeedCreate` feasibility** proven (Phase-3 de-risk).

**Handed to Stefan — 30-second UI toggles (the Linear SPA is an unreliable grind for the agent; reliable human clicks instead)**
- **#1 Native GitHub status-automation:** `fn8` → Settings → Integrations → GitHub → confirm the **remixa** repo is connected → map `PR open→In Progress` / `merge→Done` to fn8's workflow states.
- **#3 Code Intelligence:** AI Settings → enable **Code Intelligence** → select the **remixa** repo. Then add one **Triage Automation** that runs an fn8 Skill, and turn on **Triage Intelligence** auto-apply. (All free-in-beta.)

**Deferred — with reasons, not dodged**
- **Delete the PR #11 script (#1 tail):** gated on *seeing native links actually appear* (needs a real push + the remixa repo confirmed connected) — unverifiable in one session. PR #11 is a safe no-op; retire it once native linking is visibly working.
- **Feedback code scaffold (Phase 3):** gated by **GDPR/DPA + zero users** — building intake now is speculative code that would rot. Feasibility proven, design captured; build when there's a user + CLO sign-off.
- **#4 Coding Sessions eval:** spends Stefan's AI credits on a real bug and is a build-vs-buy *judgment* — needs his go.
- **#5 OAuth app → Agent:** this is the connector the **other session is actively building** — coordinate, don't double-build.
- **GDPR/DPA:** legal gate (CLO/human) before any real user feedback flows.

---

_Sources: Linear changelog & developer docs (2025–2026), cited inline; raw findings retained in the recon workflow transcripts. Capability claims marked UNVERIFIED need confirmation as noted._
