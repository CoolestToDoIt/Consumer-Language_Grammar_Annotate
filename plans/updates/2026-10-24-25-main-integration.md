# Main integration

The user explicitly requested pushing the tested combined integration into main.
Refreshed origin and verified local/remote main both pointed to `24a5a38`, with
no incoming changes outside the tested integration history. Fast-forwarded local
main to `7b95de1` without conflicts. This status-only follow-up accompanies the
requested push to origin.

The implementation is unchanged from the tested stopping point: 83 passing tests,
36 completed and verified real-language prefix runs, and exact real-corpus
interrupted/resumed equivalence. No additional test run is needed for this
fast-forward and documentation-only update. Whitespace checks pass.

Feature and integration branches are retained. The internal-stem-edit experiment
remains deferred and unimplemented; this publication does not authorize starting
it. See CURRENT and the prior stopping note for validation evidence and remaining
research work.
