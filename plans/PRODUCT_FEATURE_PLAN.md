# Product feature plan — Agents A and B

Target: a local application for importing a language corpus, reviewing word
predictions, teaching corrections, and reopening saved work. Fluent sentence
translation is a separate future scope. All features below are planned.

| Feature | Owner | Build | Done when | Status |
|---|---|---|---|---|
| 1. Persistent language workspace | **A** | Create/open/save/export projects containing corpus identity, model configuration, authoritative annotations, revisions and checkpoints. | Independent language projects reopen with identical state. | Implemented; independent reopen and backup/restore tested. |
| 2. Real-text teaching CLI | **B** | Submit sentences, inspect candidates/evidence, confirm or correct aligned glosses, and display updated predictions. | A user can teach and resume a project without editing annotation files. | Pending B. |
| 3. Local web interface | **A** | Project selection, corpus import, sentence queue, editable word glosses, candidate evidence and known/unknown indicators. | Import → predict → correct → reopen works entirely through the UI. | Implemented; loopback browser smoke test verified import, correction and reopen. |
| 4. Unknown-form learning | **B** | Run the isolated internal-stem-edit experiment, diagnose grounded-word failures and compare with the frozen baseline. | Reproducible development results support an explicit adopt/reject decision. | Deferred; not started. |
| 5. Contextual disambiguation | **A** | Use sentence context to resolve ambiguous meanings or grammatical analyses. | A fixed ambiguity benchmark improves without unacceptable baseline regression. | Implemented; fixed fixture improves 1/2 → 2/2 with no change to unambiguous words. |
| 6. Efficient review | **B** | Review ordering, calibrated uncertainty, search, annotation history and correction-conflict handling. | Users can find uncertain items, trace annotations and replace mistakes safely. | Pending B. |
| 7. Release packaging and validation | **A** | Installation/startup, example projects, backup/restore, portable exports, documentation, end-to-end checks and user trials. | A new user can install, teach, save and recover work; release limitations are documented. | Install/startup and backup/restore are automated-tested; browser smoke test complete; external user trial remains outstanding. |

## Separate work and integration

- Start separate branches from the same current main commit. Each feature gets
  its own branch; owners coordinate before editing shared files.
- First agree on a small project API: create/open, predict, correct, save and
  export. **A owns persistence; B owns teaching commands.** B can build against
  a fixture adapter while A implements storage.
- Feature 3 uses that API after 1–2 integrate. Feature 4 can proceed independently
  on an experimental branch **after approval**; it is currently deferred and
  this plan does not authorize starting it or changing the default learner.
- Define evaluation fixtures before implementing 4–5. Keep model experiments
  separate from product plumbing. Feature 6 uses project/annotation APIs and
  coordinates UI changes with A. Feature 7 follows the integrated workflow;
  B validates the teaching/review path during release review.
- Preserve existing tests, historical results and prediction-before-feedback
  behavior. Use Lezgi/Tsez development data for model work. Reserved-language
  evaluation follows a separately agreed frozen protocol.
- Update feature status and milestone notes at meaningful checkpoints. Present
  tested integration for approval before important publication/default-model
  changes. Do not treat uncalibrated scores as confidence percentages.
