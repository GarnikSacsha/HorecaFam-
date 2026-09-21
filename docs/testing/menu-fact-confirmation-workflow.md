# Menu fact confirmation — proposed next bounded workflow

## Operator flow

1. Open a new Draft copied from the current Published Menu. Show a queue grouped by missing
   composition/allergens, with category/search filters and counts. Never edit Published facts.
2. Open one item. Show its snapshot description and provenance separately from verified facts.
   The description is a clue for review, not evidence of complete composition or allergen absence.
3. A responsible venue representative supplies a recipe/technical card or explicit source decision.
   Record a source reference, date and responsible person through the approved evidence channel;
   do not put private evidence or contact details in public descriptions or logs.
4. Review composition and allergens separately. Keep unknown if evidence is incomplete.
   confirmed_present requires the actual ordered component list or controlled allergen codes.
   confirmed_none is an explicit evidence-backed absence decision, never a default or a shortcut.
5. Show the exact fact diff and source before a dedicated confirmation action. The server records
   the authenticated actor/time and provenance, preserves revision/CSRF/tenant checks and audits
   the change. Editing a name/price must not silently renew a fact-verification decision.
6. Recheck ordinary publication readiness and publish the new version. Re-evaluate affected
   Training/question dependencies through existing review/readiness rules; do not automatically
   accept regenerated questions or overwrite existing assessment history.

## What must be implemented next

The existing backend has fact completeness validation and provenance/verification fields, but the
Admin editor exposes only name/price. The next bounded issue should add the fact-review form,
source-required explicit confirmation, unknown defaults for manual creation, per-domain review
status and a truthful pending queue. Determine whether current verification persistence captures
separate domain evidence before deciding on any migration. No new table is authorized by this plan.

Acceptance must prove: ordinary edits cannot confirm facts; incomplete evidence stays unknown;
invalid present/empty-list and none/nonempty-list combinations are rejected; stale revision and
foreign-tenant actions fail; actor/time/source are retained without exposing private data;
published history is immutable; unknown facts never produce safety questions.

## Immediate demo boundary

Demo publication leaves unknown values unchanged and clearly warns the administrator. Employee
allergen reference already displays an unconfirmed message. This permits exercising navigation
and category/description learning, not relying on the snapshot for allergen advice. Venue
confirmation and full fact-review UI remain outstanding product work.
