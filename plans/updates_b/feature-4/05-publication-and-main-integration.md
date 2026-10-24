# Publishing both Worker B branches and integrating main

## What the user authorized

After reviewing the experiment, the user requested pushing both completed
branches and merging them into main. This authorizes publishing the experimental
implementation and its reports alongside the teaching/review features. It does
not require enabling the experimental learner as the application's default.

The two branches are:

- `feat/worker-b-teaching-review`: product features at `bc0a5df`.
- `experiment/gloss-internal-edits`: includes that product branch, the evaluated
  experiment at `4eb8632`, results at `32bb612`, and these publication notes.

## Why there was a regression

Internal rules share the same 512 slots with existing prefix/suffix rules. Some
useful old rules lose their slots, and additional votes can rank the wrong gloss
first. Five of the seven Tsez regressions have a baseline winning-evidence rule
that was displaced. Some apparent internal changes also occur immediately before
punctuation, so they do not establish that genuine stem morphology was learned.
No further model investigation or tuning is part of this publication request.

## Integration procedure and verification

Fetching origin confirmed remote main is still Worker A's `eaab130`, already
included in both branches. The working tree was clean. The evaluated model and
runner retain their saved fingerprints; the existing 146-test record remains
applicable because publication adds documentation and no prediction changes.

Main can fast-forward first to the teaching/review branch and then to the
experiment branch. The second branch already contains the first, so this keeps
both histories without conflict resolution or redundant merge commits.

Publish both named branches and main together with an atomic push. Verify that
local and remote main have the same commit, both published branch tips are
ancestors of main, and the working tree is clean. Keep the branches available;
do not delete them or force-push any history.

The application continues using the established learner. The experiment remains
an explicitly invoked module/tool, with **reject default adoption** recorded in
its decision report. This integration does not change that research conclusion.
