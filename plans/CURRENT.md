# Current development direction

Build an interactive language learner that can apply corrected knowledge to unseen text. The synthetic track tests selected grammar transfer under controlled conditions. The real-corpus track currently learns and evaluates lemma, POS, and morphology on English and Turkish data.

Latest status: [real-corpus validation](updates/2026-10-24-06-real-corpus-validation.md).

Real-corpus baseline joint accuracy is 88.6% for English EWT and 78.5% for Turkish IMST, with exact training-source overlaps excluded. This is supervised morphological analysis with supplied word segmentation, not arbitrary-language translation. Keep annotation budgets and corpus splits explicit.

Near-term priorities are contextual ambiguity, unseen forms, and a separately evaluated bilingual gloss/translation track. Use development data for improvement; retain test reports as the fixed baseline for the present algorithm. Continue writing updates after meaningful implementation/verification milestones.

The [original research roadmap](overview/Language_Decipherment_Build_Plan.md) provides longer-term experiments and limitations. Run instructions and corpus formats are documented in the repository README.
