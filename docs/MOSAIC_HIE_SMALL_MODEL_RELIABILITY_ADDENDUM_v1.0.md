# Mosaic HIE Small-Model Reliability Addendum v1.0

**Date:** 2026-11-02  
**Authority:** MASTER-approved continuation of HIE-0 audit  
**Related architecture:** `MOSAIC_HARNESS_IMPROVEMENT_ENGINE_ARCHITECTURE_v1.0.md`  
**Scope:** minimal persistence clarification and implementation requirements for HIE cancellation and project-scoped experiences.

## 1. Primary objective

The objective is to improve the success rate and verifiability of Mosaic Tasks even when the selected model is small and runs locally. The HIE improves the harness around the selected model; it does not modify model weights, silently switch models, or require a larger model.

Prefer improvements that reduce ambiguity and repeated work:
- concise plans with the fewest sufficient subtasks;
- explicit tool scope and testable acceptance criteria;
- deterministic checks and artifact readback before declaring success;
- reuse of relevant, evidence-backed lessons from the same project;
- bounded model calls, context, output, retries, and wall-clock time.

Do not claim general performance gains from a small fixture set. Record the provider/model and limits of each comparison.

## 2. Persistence decision

The existing HIE tables are formalized as the only HIE-specific SQLite tables permitted by this MVP contract:
- `hie_sessions`
- `hie_experiments`
- `hie_candidate_approvals`
- `hie_promotions`

The only schema migration authorized by this addendum is adding the `cancelled` value to the existing `hie_experiments.status` constraint. The migration must preserve rows and stable foreign-key targets. No fifth HIE table is authorized.

## 3. Experience library

Experiences are JSON files stored beneath the existing HIE artifact root, scoped by project. They are not user Memory and do not create new SQLite tables.

Each experience records:
- cue and curated lesson;
- project and agent-profile scope;
- source experiment, promotion, candidate hash, provider/model;
- baseline/candidate pass rates and deterministic delta;
- references to persisted Core Artifacts, verified against artifact ID, owning Task, type and SHA-256;
- a sample-size-aware heuristic confidence (explicitly not a statistical probability), limitations, lifecycle, creation/update times and a record hash.

An experience may be created only from a completed experiment whose candidate was assessed as better, has positive deterministic pass-rate delta, has persisted hash-addressed evidence, and has an active explicit promotion. Rolled-back candidates cannot create new active experiences.

RAGNES retrieves at most two relevant experiences only when HIE is explicitly enabled for the current conversation or active Task. Retrieval is lexical and bounded; results must match the same project and, where known, the active agent profile. Retrieved text is untrusted evidence, never policy or permission. Current Task verification takes precedence over historical lessons.

Listing, inspecting, deactivating and deleting experience records must not delete the original experiment evidence or source Artifacts. Integrity-invalid, ungrounded, inactive, or cross-project records are excluded.

## 4. Cancellation semantics

A draft, queued or running experiment may be explicitly cancelled. Cancellation is terminal, emits a Task/HIE event, marks the associated active Task cancelled, prevents future provider calls, disables automatic retries and promotion, and preserves partial evidence. An already in-flight provider request cannot be forcibly interrupted by this application layer; its return is discarded and no subsequent probe begins.

## 5. Small-model evaluation discipline

- Use a fixed selected provider/model and equivalent baseline/candidate inputs.
- Prefer deterministic checks over model-based judging.
- Require a positive measured result before creating a reusable experience.
- Keep experience retrieval concise to avoid increasing context indiscriminately.
- Do not store chain-of-thought, credentials or unnecessary sensitive context.
- Keep HIE opt-in and never promote automatically.
