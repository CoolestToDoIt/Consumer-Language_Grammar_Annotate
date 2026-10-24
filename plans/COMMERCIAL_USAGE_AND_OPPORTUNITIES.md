# Commercial Use and Product Opportunities

## Executive summary

Decipher Lab is currently best positioned as a **local, human-guided workbench
for word-level glossing and language-data review**. A linguist or language team
imports source sentences and any available aligned glosses, reviews model
suggestions, teaches corrections, and preserves a separate workspace for each
language.

It is not currently a fluent sentence-translation product, an autonomous
language-decipherment system, or a managed multi-user service. It needs human
annotations to ground word meanings, and its predictions should be reviewed.
The commercial opportunity is therefore workflow assistance and reusable
language resources—not replacing linguistic expertise or promising translation
from unannotated text.

## What a user can do today

The current application supports:

- Create and reopen independent language projects.
- Import UTF-8 plain text, TSV with optional aligned glosses, and SIGMORPHON
  source/gloss tiers.
- Generate word-level gloss suggestions from memory, spelling analogy, and
  prefix/suffix rules grounded in corrected examples.
- Review candidate evidence and known/unknown word forms in the browser UI.
- Teach, confirm, revise, and review glosses through the local UI and teaching
  CLI. The CLI additionally supports search, annotation history, review
  prioritization, and guarded correction replacement.
- Use limited contextual reranking based on exact neighboring-word contexts
  observed in annotations.
- Preserve annotation revisions and project state, reopen projects, and export
  or restore portable backups.
- Evaluate the gloss learner, run prediction-before-feedback experiments, and
  optionally calibrate review estimates on separate fitting and validation
  data.
- Train and evaluate morphology models on annotated corpora, and run optional
  neural experiments when PyTorch is installed.

See the [README](../README.md), [product feature plan](PRODUCT_FEATURE_PLAN.md),
and [Worker B product-feature handoff](updates_b/product-features/07-handoff-and-commands.md)
for setup commands and implementation details.

## Potential users and use cases

Potential early adopters include:

1. **Field linguists and language-documentation teams** building or curating
   interlinear glossed text.
2. **University research groups** studying low-resource morphology, annotation
   workflows, or human-in-the-loop language technology.
3. **Community language programs and archives** maintaining permissioned
   lexical and example-sentence resources.
4. **Research and nonprofit organizations** that need a local, inspectable
   annotation tool before they can justify a broader platform.

Potential workflows include organizing a small teaching corpus, surfacing
unfamiliar or ambiguous forms for expert review, reusing corrected examples
across sessions, and documenting annotation decisions. These are hypotheses
about customer needs, not validated market demand; interviews and pilots are
needed before selecting a segment or pricing model.

## Selling points to validate

- **Human remains in control:** suggestions are editable, corrections are
  authoritative, and revisions are retained.
- **Language-specific workspaces:** projects keep each language's corpus,
  settings, and annotations separate.
- **Transparent evidence:** the UI exposes candidate glosses and evidence kind
  instead of presenting raw scores as calibrated probabilities.
- **Local-first workflow:** the web interface binds to loopback, and project
  files and backups are portable. This can be valuable where data governance
  requires local handling, but does not by itself constitute a security
  certification.
- **Low setup friction for small corpora:** users can import familiar text,
  TSV, or SIGMORPHON tiers and begin reviewing without building a database.
- **Reusable teaching:** corrections are persisted and can inform later
  predictions rather than being one-off edits to a static output.

These should be sold as capabilities to evaluate, not as quantified savings,
accuracy guarantees, or claims of community endorsement until supported by
independent user evidence.

## Commercial models to explore

### 1. Paid pilot or implementation service

Start with a time-bounded pilot for one research group or language program.
Help prepare a permission-cleared sample, configure the workflow, train users,
and measure whether the tool improves their annotation process. Charge for
support and integration only after agreeing on data handling, scope, and success
criteria.

### 2. Research-group or institutional license

If multiple pilots show repeatable value, consider a paid desktop/local license
with installation help, versioned releases, documentation, and support.
Pricing should reflect measured user value and operational costs rather than
being guessed before interviews.

### 3. Grants and research partnerships

Academic or nonprofit partnerships may support evaluation, accessibility, and
community-governed development. Funding or collaboration should be structured
so language communities retain appropriate control over their data and
attribution.

### 4. Future hosted collaboration offering

A managed service could support teams, roles, synchronization, and shared
projects, but this is a substantially different product. Do not imply that the
current local prototype already provides accounts, remote storage, team
collaboration, or hosted availability.

## Highest-priority improvements before selling broadly

### Product reliability and usability

- Conduct observed trials with linguists and intended community users. Record
  task completion, confusion points, import failures, correction effort, and
  backup recovery—not just model accuracy.
- Improve corpus import feedback: encoding, token/gloss alignment, duplicate
  imports, large files, malformed records, and actionable error messages.
- Add explicit project-level export formats and documented restore/version
  compatibility; test backups through recovery on a clean installation.
- Improve navigation and scaling for large queues, including filtering,
  pagination, keyboard accessibility, and clear distinction between
  unreviewed, reviewed, and conflicting examples.
- Provide clear onboarding with a disposable example project and explain which
  corpus formats preserve source segmentation.

### Language-data governance

- Define a data-handling policy before pilots: ownership, consent, license,
  retention, deletion, backups, and who may access project files.
- Make provenance and license metadata first-class project information.
- Avoid bundling user corpora or trained artifacts without explicit rights.
- Support community-directed terminology and annotation conventions rather
  than assuming one glossing standard fits all languages.
- Provide a clear deletion and portable export path so teams can leave without
  losing access to their data.

### Model quality and claims

- Evaluate on permissioned, independently held-out languages and report
  denominators, unknown-form performance, annotation exposure, and error
  categories.
- Continue separating train, calibration, development, and test data; never
  use reserved evaluation annotations for product tuning.
- Validate contextual ranking on a larger, fixed ambiguity benchmark and
  document when it lacks evidence.
- Improve support for language-specific segmentation, orthography, tokenization,
  and annotation schemas.
- Keep raw scores labeled as uncalibrated. Only expose empirical accuracy
  estimates when a matching, valid calibration artifact exists.
- Do not adopt the internal-stem-edit experiment as the default learner: its
  preregistered evaluation rejected default adoption. See the
  [experiment decision](updates_b/feature-4/03-results-and-decision.md).

### Security and operations

- Treat local-only binding as a current design constraint, not a complete
  security review. Review file permissions, backup handling, browser request
  protections, dependency updates, and threat assumptions before wider
  distribution.
- Package reproducible releases with supported Python versions, dependency
  guidance, upgrade instructions, and data migration policy.
- Add crash/recovery tests around project writes, imports, backup restore, and
  interrupted upgrades.
- If collaboration or hosted storage is ever added, design authentication,
  authorization, encryption, audit, isolation, retention, and incident
  response before implementation.

## A practical validation and go-to-market sequence

1. **Interview:** speak with several intended users about their existing
   annotation tools, data formats, bottlenecks, and purchasing constraints.
2. **Pilot:** select one permissioned, representative corpus and define a
   bounded evaluation with the user before importing their data.
3. **Measure:** compare the current workflow and the assisted workflow on
   annotation time, corrections accepted, errors caught, import success, and
   recovery. Report sample sizes and limitations.
4. **Review governance:** confirm community and institutional permission,
   licensing, storage, backup, and attribution expectations.
5. **Decide:** continue, narrow, or stop based on user value and operational
   fit. Only then select pricing, support commitments, and packaging.

Do not promise a percentage of time saved, a specific accuracy on a buyer's
language, fluent translation, or broad language coverage without directly
relevant measured evidence and the user's agreement on evaluation criteria.

## Current limitations to disclose

- The gloss workflow predicts word-aligned labels; it does not generate fluent
  sentence translations.
- Meaning predictions require human-provided aligned examples as semantic
  anchors. Raw text alone cannot teach arbitrary source-to-English meaning.
- Contextual disambiguation is a limited exact-neighbor method, not general
  sentence understanding.
- Lezgi and Tsez evidence is development evaluation, not proof of performance
  on a prospective customer's language.
- The application is a local prototype, not a hosted multi-user product.
- An external user trial remains outstanding in the
  [product feature plan](PRODUCT_FEATURE_PLAN.md).
- Corpus and trained-artifact redistribution depends on the source material's
  license and permissions.

## Commercial readiness checklist

- [ ] Complete observed user trials with permissioned data.
- [ ] Validate usefulness and workflow fit with more than one target group.
- [ ] Publish an honest model evaluation protocol and language-specific limits.
- [ ] Document data ownership, licenses, retention, backup, and deletion.
- [ ] Test clean-install, upgrade, export, and restore paths.
- [ ] Complete a security/privacy review appropriate to the distribution
  model.
- [ ] Define support, maintenance, compatibility, and release policies.
- [ ] Select pricing only after value and buyer constraints are understood.
