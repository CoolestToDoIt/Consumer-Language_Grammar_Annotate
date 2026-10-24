# Real-text teaching CLI: first completed feature

## What works

The new `gloss teach` commands and interactive shell use the typed project
adapter. A person can submit a source sentence, inspect every candidate and its
evidence, enter aligned word glosses, confirm a complete prediction, revise an
answer with a reason, inspect history, save, reopen and export.

The opt-in fixture backend makes this runnable before A's production workspace
exists. It is explicitly a development backend, not a new production persistence
format. A can inject its store into `teaching_app.main(..., store=...)` or expose
the proposed `decipher.workspace.WorkspaceStore` interface.

## Safety behavior

- First predictions are stored before answers and remain unchanged after teaching.
- Incomplete/unknown output cannot be confirmed as a complete answer.
- Existing source IDs cannot be reused for different words. Unicode is normalized.
- Old annotation revisions and confirmation of old model predictions are rejected.
- Replacing a different verified answer requires a replacement choice and reason.
- A retry operation ID does not teach twice; it cannot be reused for a different
  request. Revisions remove superseded evidence rather than accumulating it.
- The fixture uses atomic saves, an exclusive writer lock and a saved-file identity
  check, so stale clients cannot silently replace saved work. A leftover fixture
  lock after a crashed process is reported instead of being stolen automatically.

## Checks

The first 11 teaching tests passed, including a complete standard-library-only
CLI/shell flow and save/reopen/export equality. A twelfth test now covers a writer
lock owned by another process; the combined suite is the next verification step.
The baseline was 83 passing tests. The default learner and historical evaluation
implementation are unchanged.

Combined verification has now completed: **95 tests passed** (83 existing plus
12 teaching tests), including all optional neural tests. Feature 2's code and
fixture contract are ready for review on `feat/real-text-teaching-cli`; the
umbrella branch will collect B's related product work without changing main.

## Try the development flow

Use a fresh path under ignored `runs/`:

```powershell
.venv/Scripts/python.exe -X utf8 -S -m decipher.app gloss teach init --project runs/teaching-demo.fixture.json --backend fixture --name "My language" --language "Demo"
.venv/Scripts/python.exe -X utf8 -S -m decipher.app gloss teach shell --project runs/teaching-demo.fixture.json --backend fixture
```

Inside the shell:

```text
submit anchors tal mir
predict anchors
correct tree bird
submit plural talum
predict plural
correct tree-PL
submit probe mirum
predict probe
confirm
history probe
quit
```

Reopen with the same shell command. Source words are whitespace segmented. Raw
candidate scores are printed as uncalibrated numbers, never confidence percentages.
Production persistence/UI integration remains A's responsibility under the plan.
