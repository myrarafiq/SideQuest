# Side Quest: Complete Project Context for Cursor

Side Quest is an NYC-first activity-discovery and group-decision product. It helps people turn free time and “we should hang out” into a fair, practical plan by combining local activity data with participants’ availability, budgets, starting areas, travel limits, and interests.

Document date: October 13, 2026. This is a consolidated product and implementation brief, not a claim that the product, integrations, model, or partnerships already exist.

## How Cursor should use this document

Read this document before implementing features, changing product behavior, or selecting integrations. Use it as the project context, while treating the current repository, explicit owner decisions, and newer instructions as authoritative for what has actually been built.

- **Established direction:** Repeatedly expressed product goals and core experience in the project discussions.
- **Recommended MVP default:** Concrete implementation guidance proposed here to make the concept buildable; not an already approved team decision.
- **Access-dependent:** An integration that requires credentials, permissions, subscriptions, provider-term review, or organizer agreement.
- **Future / explored:** An idea discussed but not committed to the initial product.
- **Unknown:** A decision or capability that has not been confirmed; do not invent it.

Before coding, inspect the repository, dependencies, existing screens, schema, tests, configuration, and project instructions. Preserve useful existing work rather than rebuilding around an assumed stack.

Do not infer that a feature exists because it appears in a pitch or UI mockup. Never fabricate real venue prices, live inventory, completed API calls, model accuracy, user traction, or partnerships; label fixtures and demo mode clearly.

## Problem statement

When people have free time but no plan, they face a fragmented and socially awkward coordination problem. Existing habits involve group-chat messages, social-media links, maps, calendars, polls, and booking websites, while one “default planner” has to reconcile everyone’s constraints.

The cost is not simply lack of ideas. It is the effort of finding a time, comparing budgets and travel, guessing what friends actually want, dealing with “I don’t mind,” narrowing too many options, and converting conversation into a decision.

The user need is a fast, low-effort, pressure-free way to discover worthwhile activities and turn different schedules, budgets, locations, and preferences into one fair, actionable plan. The original reference phrase about “forming auditable, balanced teams” came from a different class example and is not Side Quest’s problem.

### Product proposition

> Side Quest helps friends discover things to do and agree on a plan that fits everyone, without the coordination burden and social pressure of group-chat planning.

The defining principle is feasibility before voting. Swiping is the decision interface, not the underlying innovation.

```text
Local activities + participant constraints
                    ↓
             Feasible shortlist
                    ↓
       Fair, explainable group ranking
                    ↓
          Private swipe / mutual match
                    ↓
             Actionable final plan
```

### Two connected use cases

- **Discovery:** “I’m bored or have free time. What could I do?”
- **Group coordination:** “We want to hang out, but cannot agree on when, where, or what.”

The core MVP is the group-room flow. Preserve the discovery proposition, but do not automatically add a separate solo feed, social network, or standalone recommendation journey.

## Goals

The desired outcomes are less planning effort, faster decisions, honest preference expression, fairer practical compromises, and more outings that actually happen. These are product goals, not measured outcomes from an existing pilot.

- **Coordination efficiency:** Reduce the manual work done by the default planner.
- **Decision speed:** Help a group reach a usable decision in minutes; the earlier “under two minutes” aspiration is a hypothesis, not a validated guarantee.
- **Group feasibility:** Avoid presenting confidently “matched” plans that violate someone’s non-negotiables.
- **Social harmony:** Let participants say no privately without publicly defending their budget or preferences.
- **Actionability:** End with a concrete activity, attendance time, location, cost information, and official next steps.

## Audience and initial scope

The established starting audience is college students and young adults, including young professionals, in New York City. The strongest initiating persona is the friend who repeatedly organizes casual outings.

Groups spread across residence halls and neighborhoods are a motivating example. The product should consider everyone’s starting area rather than optimizing around the organizer’s location.

| Dimension | Direction | Status |
|---|---|---|
| Geography | NYC first | Established |
| Initial coverage | A manageable set of neighborhoods with sufficiently reliable supply | Recommended MVP default; exact boundaries unresolved |
| Users | Students, young adults, young professionals, and their friend groups | Established |
| Group size | Roughly 3–8 people was discussed | Proposed range; not a finalized enforcement rule |
| Planning horizon | Tonight, the weekend, or a near-term custom window | Established direction |
| Experience | Mobile-first, lightweight room accessed from a shared link/code | Established direction |
| Platform | Responsive web application is the lowest-friction proposed starting point | Recommended, not a confirmed stack decision |
| Booking | Handoff to official providers | Established MVP direction |

### Activity categories

- **Food and drink:** Casual restaurants, cafés, and age-appropriate bars.
- **Activities:** Arcades, bowling, games, mini golf, classes, and workshops.
- **Culture:** Museums, galleries, exhibitions, films, music, comedy, and performances.
- **Public and outdoor programming:** Parks activities, public events, and other low-cost options.
- **Temporary local events:** Pop-ups, markets, one-off happenings, tech talks, and community conversations.

The owner wants coverage beyond permanent venues, including smaller events happening now. That is a supply ambition, not a promise of complete citywide coverage at launch.

## Non-goals

Keep the initial product focused on discovery, feasibility, agreement, and handoff. Do not add the following without an explicit request.

- **Messaging replacement:** No replacement for iMessage, WhatsApp, SMS, Discord, or Instagram DMs.
- **Social network:** No public friend graph, dating, stranger matching, or public vote feed.
- **Booking business:** No in-app ticket sales, reservation inventory ownership, payment processing, deposits, refunds, or cost splitting.
- **Travel planner:** No full multi-day itineraries or long-distance trip planning.
- **Universal live coverage:** No claim to ingest every NYC event or guarantee current ticket/table availability.
- **Calendar replacement:** No full calendar-account integration required for the MVP.
- **Advanced AI dependency:** No requirement to build an LLM planner or trained recommender before the room flow works.

## User stories

| Priority | User story |
|---|---|
| P0 | As an organizer, I want to create and share a room quickly so I do not have to coordinate everything manually. |
| P0 | As a friend, I want to join from the group-chat link without a lengthy account setup so participating feels easy. |
| P0 | As a participant, I want to set my time, budget, starting area, travel limit, and interests so the shortlist reflects my needs. |
| P0 | As a budget-conscious participant, I want my hard cap respected without needing to justify it publicly. |
| P0 | As a participant, I want to vote privately so I can honestly reject an option without awkwardness. |
| P0 | As a group, we want a short set of realistic choices rather than an overwhelming activity directory. |
| P0 | As a group, we want a mutual match and a clear plan with directions and official booking information. |
| P0 | As a group with no match, we want understandable next steps without anyone’s hard constraints being silently overridden. |
| P1 | As a participant, I want to understand uncertainty in price, accessibility, travel, and availability before committing. |
| P1 | As an organizer, I want to see who is ready without seeing each person’s private votes and sensitive inputs. |

## Requirements and feature mapping

Requirements describe what users need. Features describe the mechanisms used to satisfy those needs; a feature that serves no requirement is decoration.

| ID | User requirement | Proposed supporting features |
|---|---|---|
| R1 | Low-effort participation | Quick room creation, guest join, shareable link/code, short intake |
| R2 | Fast decisions | Limited deck, simultaneous independent voting, automatic match detection |
| R3 | Low decision fatigue | Feasibility-first filtering, ranked shortlist, useful no-match state |
| R4 | Practical group compatibility | Shared availability, individual budget and travel limits, status/time validation |
| R5 | Personal control | Hard-versus-flexible settings, editable preferences, private rejection |
| R6 | Low social pressure | Hidden individual votes and privacy-preserving group summaries |
| R7 | Fair outcomes | Group-level interest aggregation, average and worst-case travel consideration |
| R8 | Transparent recommendations | “Why this fits,” explicit trade-offs, clear unknown fields |
| R9 | Current-enough information | Source attribution, collection/check timestamps, stale/expired handling |
| R10 | Existing-chat accessibility | Universal room link, code entry, copy/share final plan |
| R11 | Actionable final outcome | Activity, time, address, price information, directions and official booking handoff |
| R12 | Recovery from disagreement | Closest feasible options, explicit preference edits, new deck version |

### Functional scope

P0 is the essential vertical slice. P1 items are optional follow-ups after that slice works; future ideas are not required for delivery.

| Priority | Feature | Boundary |
|---|---|---|
| P0 | Create/join room | Guest-capable room link and code |
| P0 | Participant intake | Manual availability, budget, starting area, travel limit, interests |
| P0 | Feasibility engine | Hard filtering with explicit handling of missing evidence |
| P0 | Group ranking | Explainable rules-based score |
| P0 | Small recommendation deck | Recommended default: up to 8 cards, configurable; earlier proposals ranged from 5–15 |
| P0 | Private yes/no voting | Button controls as well as optional swipe gesture |
| P0 | Automatic unanimous match | Recommended MVP rule; not a final approved policy |
| P0 | Matched plan | Official links and truthful cost/time/status fields |
| P0 | No-match recovery | No silent constraint relaxation or organizer override |
| P0 | Real data ingestion path | At least one reproducible source adapter or import |
| P1 | Live route estimates | Provider integration if available; honest estimate mode otherwise |
| P1 | Total-budget mode | Only when transport-cost inputs and uncertainty handling are adequate |
| P1 | Organizer submission/import interface | Minimal reviewed supply intake, not a marketplace |
| P1 | Calendar export | Single plan export, not calendar-account sync |

### Future or explored features

Calendar sync, saved groups, historical personalization, weather-aware plans, advanced vote types, timers or “Plan Lock,” natural-language requests, social-link extraction, multi-stop mini-adventures, live reservation/ticket capacity, reminders, payments, deposits, and cost splitting were brainstormed. None should automatically become committed MVP scope.

Accessibility, dietary needs, and age restrictions matter whenever the product claims to support them. A full automated verification system is not established; never offer a hard filter whose data coverage cannot substantiate it.

## End-to-end user flow

### Create and share

The organizer enters a lightweight room name and planning context. The product creates a room and offers a room link/code that can be pasted into the existing group chat.

Native chat integration is not required. Recommended implementation is a browser-based join page, copy-link controls, and system sharing where available, with a copy fallback.

### Join and enter preferences

A participant joins with a nickname or lightweight guest identity and enters the minimum information required for planning. Avoid unnecessary email, account, exact-home-address, or calendar-permission requests.

| Input | Intended meaning | Notes |
|---|---|---|
| Availability | One or more explicit free windows | Manual input first; preserve timezone |
| Budget | Per-person maximum, with optional softer ideal | Never confuse ideal and hard cap |
| Starting area | Neighborhood or user-selected approximate origin | Exact location optional, not mandatory |
| Interests | Preferred categories | Soft preferences unless explicitly excluded |
| Maximum travel time | Individual allowable travel burden | Distinguish hard limit from flexible preference |
| Travel mode | Transit, walking, or supported option | Optional according to routing implementation |
| Hard exclusions | Supported non-negotiables | Require adequate evidence and privacy safeguards |

The organizer can see readiness and participant count. Sensitive values and individual votes should not be exposed by default; this is a recommended privacy policy pending owner approval.

### Generate the deck

Compute a shared time window, obtain candidates, normalize and validate them, evaluate hard constraints, rank the remaining options, and present a short deck. If evidence is incomplete, do not silently classify a candidate as verified feasible.

Show useful loading, error, and empty states. If only three valid candidates exist, show three rather than padding the deck with invented or incompatible options.

### Vote independently

Each participant votes yes or no on a stable, shared candidate deck. Missing votes are pending, not yes and not no.

Recommended MVP behavior is unanimous yes among the locked active voting cohort. Hidden votes reduce public pressure, but the backend still needs pseudonymous participant identities to count votes correctly.

### Match and hand off

When a candidate satisfies the match rule, persist the result and show a plan page. The plan is group-approved, not necessarily booked.

Include activity title, attendance time, address, price information, travel information where available, group-fit reasoning, uncertainty caveats, source/check information, directions, official booking/registration link, and shareable result text.

### Recover when there is no match

Treat zero feasible candidates and zero unanimous votes as different outcomes. Explain the relevant next steps without revealing who rejected what.

If constraints change or the cohort changes, generate a new version and invalidate incompatible previous votes. A participant must explicitly approve changes to their own hard limits.

## Decision engine

### Pipeline

```text
Acquire / import
    → Normalize
    → Deduplicate
    → Validate status, time, evidence, and permitted use
    → Compute group window and per-person costs/travel
    → Evaluate hard constraints
    → Rank feasible candidates
    → Diversify and limit the deck
    → Collect private votes
    → Match or recover
```

### Hard constraints versus soft preferences

| Hard constraint example | Soft preference example |
|---|---|
| Cannot spend above a specified amount | Prefer an inexpensive option |
| Only available within specified windows | Prefer an earlier start |
| Cannot travel longer than a specified limit | Prefer a nearby neighborhood |
| Must meet a supported access requirement | Prefer a quiet venue |
| Cannot attend an age-restricted event | Prefer music over games |

A good interest score cannot compensate for a failed hard constraint. “Closest fit” is not permission to exceed a hard budget or travel cap.

### Time feasibility

Intersect participants’ availability and the room’s intended planning window. Fixed-time events must fit according to an explicit attendance policy; permanent venues need a proposed visit time and enough supported opening time for the activity.

Recommended default is full event attendance unless explicitly changed. Travel-before-arrival and activity-duration assumptions must be stated rather than silently guessed.

Store absolute timestamps with timezone-aware interpretation and render NYC plans in America/New_York. Do not substitute permit setup times for public attendance times, or assume missing event end times imply a feasible duration.

### Budget feasibility

Start with activity-only caps and display travel separately. Total-budget mode is an extension requiring per-person transport estimates and explicit treatment of uncertainty.

\[
C_i = A_i + T_i + F_i
\]

Here \(A_i\) is the participant’s activity cost, \(T_i\) is transport cost when applicable, and \(F_i\) is known relevant fees. A cost estimate must identify its inclusions, currency, per-person versus per-group basis, and whether transportation is one-way or round-trip.

For a known range, the lower bound alone cannot prove budget compliance. Recommended conservative policy is to use a relevant upper bound or require review; missing prices are not zero, and venue price categories are not exact bills.

Restaurant totals, taxes, gratuities, booking fees, minimum purchases, and multi-stop costs may be unknown. Clearly separate confirmed admission from optional spending and do not promise that a restaurant outing stays below a hard total cap without adequate evidence.

### Travel feasibility and fairness

Check each person’s travel limit independently. A low average cannot make a plan feasible when one participant exceeds their hard cap.

Rank using average duration and worst individual duration, with travel spread optionally included. Evaluate routes to candidate destinations; a geographic midpoint is not automatically the fairest transit destination.

If approximate neighborhood travel is used, label it estimated and do not claim strict route verification. Missing routing data needs an explicit unknown/review policy, not a fabricated duration.

### Evidence and uncertainty

Recommended internal outcomes are `pass`, `fail`, and `unknown` for every supported constraint. Aggregate them into `verified_feasible`, `needs_review`, or `infeasible`.

Exclude known failures from the normal deck. Prefer verified feasible items; uncertain items may only appear in a clearly separate, explicitly enabled review path and must never be described as satisfying all hard constraints.

Knowing a venue is open does not establish table capacity. Having an event listing does not establish that enough tickets remain for the group.

### Ranking

Use an explainable rules-based baseline before training a model. Candidate ranking factors discussed are group interest fit, budget comfort, travel fairness, time fit, and information freshness/confidence.

\[
S(c) = w_I I(c) + w_B B(c) + w_T T(c) + w_W W(c) + w_Q Q(c)
\]

Normalize components to a documented scale and keep weights configurable. Earlier numerical weights and “92% group fit” examples were illustrative, not validated probabilities; prefer plain fit labels or clearly labeled internal scores.

Consider every participant and penalize poor worst-person outcomes rather than using only a group average. Diversify the short deck so it is not eight near-identical restaurants.

### Explanations

Generate explanations from actual checks and score components. An LLM is not required, and any future generated wording must be grounded in those checks.

Examples of defensible explanations include “matches three participants’ selected categories” or “within confirmed admission caps.” Do not say “everyone is free,” “accessible,” “within all budgets,” or “tickets available” unless the underlying evidence supports that statement.

## Matching, room lifecycle, and fallback behavior

The following is a recommended implementation policy. Exact timeout, threshold, late-join, and roster-management rules still need owner approval.

### Room lifecycle

```text
draft → collecting_preferences → generating_deck → voting
                                                ↘ no_candidates
voting → matched → archived
       ↘ no_consensus → revising_preferences → generating_deck
```

Expiration, cancellation, and recoverable errors should be explicit states or transitions. Do not implement irreversible auto-finalization timers without a product decision.

### Cohort and voting integrity

- **Cohort:** Lock the active voting participants when a round begins.
- **Late joins:** Queue for a new round or require an explicit restart; never silently change the unanimous-vote denominator.
- **Vote identity:** Store votes against room, round, participant, and candidate identifiers.
- **Idempotency:** Prevent duplicated taps or network retries from creating multiple votes.
- **Match race:** Select and persist a single result atomically, using a documented deterministic tie-breaker.
- **Vote edits:** If enabled, edits before finalization must recompute consensus; do not silently change a matched plan afterward.
- **Departures:** Never convert a disconnect into approval; roster changes require an explicit policy and visible new round.
- **Fact changes:** Material changes to event time, price, status, or location must trigger revalidation and potentially a new round.

### No candidates

Explain that no options satisfy the current supported constraints, rather than pretending to know one participant is the sole cause. Offer time/category changes or explicit user-owned limit changes, without exposing sensitive individual inputs.

### No consensus

Show the strongest still-feasible alternatives as suggestions, not a match. Let the group start a new round, change flexible preferences, or explicitly adopt a different voting policy.

An organizer-selected option is not unanimous approval. Any future override must be labeled and must not violate another person’s hard constraints or falsely imply their consent.

## Data sources

The latest proposed stack is a foundation of venue data, ticketed events, public programming, local supply, routing, and first-party preferences. These integrations are planned, not confirmed working connections.

### Core and proposed acquisition sources

| Source | Information / role | Access and limitations |
|---|---|---|
| Google Places API (New) | Permanent venue names, types, addresses, coordinates, status, hours, and available price fields | Fields and billing classifications are documented in the [Google field reference](https://developers.google.com/maps/documentation/places/web-service/data-fields). |
| Ticketmaster Discovery API | Event identifiers, titles, dates, categories, venues, booking URLs, status, and supplied price ranges | Official API-key-based event discovery; listed events do not guarantee inventory for a group ([Ticketmaster documentation](https://developer.ticketmaster.com/products-and-docs/apis/discovery-api/v2/)). |
| NYC Parks Public Events: Upcoming 14 Days | Public programming with event dates, categories, locations, links, and registration information | Official upcoming-two-week dataset; public does not automatically mean free ([NYC Open Data](https://data.cityofnewyork.us/City-Government/NYC-Parks-Public-Events-Upcoming-14-Days/w3wp-dpdi)). |
| Direct venue and organizer calendars | Target facts for pop-ups, exhibitions, markets, workshops, talks, and smaller events | Proposed approved RSS/ICS feeds, exports, submissions, or permitted manual collection; specific partners are not selected. |
| University, student-club, tech-community, and coworking calendars | Target facts for student-friendly and community events | Proposed local supply; verify eligibility, public access, and RSVP restrictions. |
| Organizer submissions | Structured event facts, source links, organizer identity, updates, cancellations | Proposed intake with review; no established partnerships claimed. |
| Team-curated records and user-submitted links | Initial verified candidates and long-tail discovery leads | Proposed manual collection with provenance; links do not grant unrestricted extraction rights. |
| Google Routes API | Travel duration, route details, and supported transit fares | Fare estimates are returned only when fare information is available for all relevant steps ([Google transit routing](https://developers.google.com/maps/documentation/routes/transit-route)). |
| Participants’ own inputs | Availability, budgets, starting areas, interests, travel limits, supported hard needs | Direct collection in the room with data minimization and appropriate consent. |
| Side Quest interaction data | Candidate exposures, private votes, round decisions, optional follow-through | Instrument actual usage; do not invent preference labels or attendance. |

Google Places content is subject to storage, caching, and attribution restrictions, while place IDs are exempt from caching restrictions ([Google Places policies](https://developers.google.com/maps/documentation/places/web-service/policies)). Normalizing a record does not remove its original licensing or retention obligations.

### Supplemental and access-dependent sources

- **NYC Events Calendar API:** Additional city-sponsored events; the portal directs developers to subscribe to a product ([NYC API portal](https://api-portal.nyc.gov/)).
- **NYC Permitted Event Information:** Upcoming approved applications; start/end fields often represent setup and breakdown, so verify public attendance details with the organizer ([NYC dataset documentation](https://data.cityofnewyork.us/City-Government/NYC-Permitted-Event-Information/tvpp-9vvx)).
- **MTA schedules and real-time feeds:** Optional schedule, disruption, and alert context; these are feeds, not a ready-made routing engine ([MTA developer resources](https://www.mta.info/developers)).
- **MTA fare information:** Potential verified fallback for transport estimates; recheck applicable current rules and do not reuse old illustrative fare numbers.
- **Luma:** Organizer-calendar integration requiring Luma Plus and calendar-scoped keys, not unrestricted NYC-wide API discovery ([Luma documentation](https://docs.luma.com/reference/getting-started-with-your-api)).
- **Eventbrite:** Authorized known-event and organizer-related retrieval; public Event Search was shut down, with documented alternatives and partner access paths ([Eventbrite changelog](https://www.eventbrite.com/platform/docs/changelog)).
- **Meetup:** Potential community integration; API access is listed as a Pro feature, with reuse governed by API terms ([Meetup documentation](https://www.meetup.com/graphql/)).

### Explored alternatives, not committed integrations

Foursquare, Yelp, and OpenStreetMap were explored as place-layer alternatives. PredictHQ was an event-aggregation candidate, Mapbox a routing alternative, Citi Bike GBFS a future bike-share candidate, and Uber/Lyft/taxi sources possible future transport-cost options.

DICE, POSH, FLITE, Fever, and Partiful were mentioned as discovery or partnership candidates. Time Out New York, local newsletters, Instagram, and TikTok were discussed as discovery leads; no approved integration or scraper for these is established.

Beli, Cobble, and CrewCal are competitor references, not selected data suppliers. Resy, OpenTable, ticket sellers, and map applications may be outbound handoff destinations without being ingestion integrations.

### Extraction policy

Prefer official APIs, open datasets, approved organizer feeds, and direct submissions. Evaluate website extraction source by source for terms, rights, privacy, access restrictions, robots guidance, and appropriate request rates.

Do not bypass authentication, CAPTCHAs, paywalls, or access controls. Do not assume that public pages, photos, descriptions, attendee lists, or social posts can be copied or used for model training.

Record which sources failed or could not be accessed. Partial source coverage is preferable to fabricated completeness.

## Data model and contracts

This is a suggested logical model, not an existing database schema. Adapt names and storage to the actual repository and provider terms.

### Core entities

| Entity | Suggested fields |
|---|---|
| Room | ID, display name, code, status, organizer identity, planning window, timezone, round/version, expiry |
| Participant | Pseudonymous ID, room ID, display name, role, readiness, session binding |
| ParticipantPreference | Availability windows, hard budget, ideal budget, budget mode, currency, starting area, travel mode/limit, interests, supported exclusions, version |
| Candidate | Canonical ID, kind, title, categories, location, venue, time/hours, cost facts, restrictions, status, official URLs |
| SourceRecord | Provider and source ID, source URL, collection/check timestamps, permitted retention, field provenance, source status |
| CandidateEvaluation | Participant-specific pass/fail/unknown checks, derived cost/travel, group components, reasons, version |
| DeckRound | Room/round ID, locked cohort, ordered candidate snapshots/references, preference version, generation status |
| Vote | Room/round, participant, candidate, yes/no, timestamp; unique vote key |
| MatchedPlan | Room/round, selected candidate, agreed attendance time, matching rule, approval state, last validation |
| InteractionEvent | Event name, pseudonymous actor, room/round/candidate IDs, timestamp, safe metadata |

### Candidate field guidance

Preserve distinctions between a permanent venue, a dated event, and any future multi-stop plan. Do not flatten opening hours into event dates or mix a per-group price with a per-person price.

```text
id
kind: venue | event
title
categories[] and original_source_categories[]
venue_name
address / neighborhood / latitude / longitude
event_start_at / event_end_at / timezone
opening_hours_reference
proposed_visit_start_at / estimated_duration_minutes
price_min / price_max / currency
price_basis: per_person | per_group | unknown
price_status: confirmed | estimated | unknown
price_inclusions / fees_status
business_or_event_status
age_restrictions / accessibility_evidence / capacity_status
official_url / booking_url
source_references[]
collected_at / last_checked_at / source_updated_at
verification_status
retention_policy_reference
```

Use null for unknown values, not invented zeroes or empty factual claims. Keep money in a consistent exact representation, and retain field-level provenance for conflicting source facts.

Any schema fields above are target needs. Do not imply every provider returns every field; some facts must remain unknown or require manual verification.

### Deduplication

Prefer provider IDs and official links, then use normalized title, venue, location, and event time as possible duplicate signals. Preserve recurring dates and multiple showtimes as distinct events.

Merge cautiously and preserve source lineage. Avoid copying restricted provider content into a permanent combined store when the provider does not permit that retention.

## Recommended architecture

No final technology stack has been approved. The safest default is a small mobile-first web application with server-side provider adapters and an independently testable decision engine.

```text
Mobile-first client
    → Room/session API
    → Preference and vote services
    → Feasibility + ranking engine
    → Match service
    → Plan/share view

Server-side provider adapters / permitted imports
    → Source-specific validation and normalization
    → Terms-aware references or retained records
    → Candidate retrieval and refresh
```

If the repository has no stack, a TypeScript web stack with a relational store is a reasonable proposal, not a requirement. Choose framework, database, deployment, and real-time mechanism only after repository inspection and owner clarification where needed.

- **Isolation:** Keep provider-specific logic out of the ranking engine and UI.
- **Validation:** Validate external records and participant input at trusted boundaries.
- **Real-time updates:** Use the existing supported mechanism or a simple polling baseline; multi-user correctness matters more than adopting new infrastructure.
- **Jobs:** Separate ingestion/refresh from interactive room decisions where practical.
- **Errors:** Handle timeouts, malformed responses, quota limits, and unavailable providers without inventing data.
- **Secrets:** Keep provider credentials server-side and out of browser bundles, shared Markdown, logs, and version control.
- **Configuration:** Keep source activation, score weights, deck size, refresh policy, and voting policy configurable.
- **Demo mode:** Allow deterministic, labeled fixtures for development; never silently fall back from live data to fake listings.

### Suggested API surface

This is an implementation proposal. Reuse existing routes if they already serve these responsibilities.

```text
POST   /api/rooms
POST   /api/rooms/join
GET    /api/rooms/:roomId
PUT    /api/rooms/:roomId/me/preferences
POST   /api/rooms/:roomId/rounds
GET    /api/rooms/:roomId/rounds/:roundId/deck
PUT    /api/rooms/:roomId/rounds/:roundId/votes/:candidateId
GET    /api/rooms/:roomId/result
POST   /api/rooms/:roomId/restart
```

Authorize each request against the participant’s room-bound session. A room code permits an appropriate join flow, not unrestricted access to private preferences or administrative operations.

Return participant-safe representations rather than serializing database rows directly. Include round and preference versions so stale requests can be rejected or retried intentionally.

## Privacy, anonymity, and security

The established goal is low-pressure preference expression. Private voting is part of the concept, but complete anonymity, organizer visibility, and retention rules have not been finalized.

Recommended defaults hide individual yes/no votes, budgets, exact origins, and sensitive constraints from other participants. Allow nicknames and readiness status, and show aggregate reasoning only when it does not disclose a private need.

“Anonymous to other participants” is different from “unidentifiable to the backend.” Do not promise complete anonymity while storing identifiable sessions or analytics.

- **Guest access:** Use secure, room-scoped session credentials; a nickname alone is not authorization.
- **Join protection:** Use adequate code entropy, expiry, and rate limiting against guessing.
- **Minimization:** Prefer neighborhoods over exact homes and manual free windows over private calendar contents.
- **Isolation:** Participants cannot read or change another person’s input or vote.
- **Sharing:** Public/shared plan views must exclude private inputs and individual vote history.
- **Retention:** Define room/session retention and deletion; do not retain guest preference histories indefinitely by default.
- **Consent:** Obtain appropriate consent for pilots and any reuse of preference or behavioral data.
- **URL imports:** If added, protect against unsafe server requests and do not fetch arbitrary internal URLs.
- **Logging:** Do not log secrets, precise locations, private calendar details, or sensitive inputs unnecessarily.

## UI and UX direction

The earlier design prompt proposed a warm, playful, premium consumer interface, not a corporate scheduling dashboard or dating-app clone. These visual choices are guidance rather than an approved Figma design system.

| Token / style | Proposed direction |
|---|---|
| Background | Warm cream, example `#F7F1E8` |
| Text | Espresso/charcoal, example `#1D1910` |
| Main accent | Muted terracotta, example `#BD866A` |
| Secondary accents | Dusty olive, lavender, and soft gold |
| Typography | Clean modern sans serif; use an existing licensed project font |
| Components | Rounded cards, restrained shadows, simple icons |
| Tone | Friendly, concise, confident about known facts, honest about uncertainty |
| Layout | Mobile-first and responsive; earlier prototype reference was approximately 390 × 844 |

Validate actual contrast rather than assuming the proposed colors are accessible. Provide visible focus, semantic controls, readable labels, and button alternatives to swipe gestures.

### Screens

| Screen | Purpose and key content |
|---|---|
| Home | Explain the value; create room or join by code |
| Create room | Name, plan context, intended time, lightweight group setup |
| Invite/lobby | Link/code, participant count, readiness, no unnecessary account gate |
| Personal intake | Availability, budget, starting area, travel limit, interests, supported hard needs |
| Group readiness | Privacy-safe progress and shared planning window |
| Generation | Honest loading/progress; no fake completed validation |
| Swipe deck | Shortlist, card facts, reasons, uncertainty, yes/no buttons and gestures |
| Match | Celebrate mutual approval without implying a completed booking |
| Plan details | Time/place/cost, source/check data, directions, official links, share |
| Recovery | Distinguish no candidates, no consensus, partial data, and provider failure |

Saved/Profile tabs, maps of individual origins, maybe votes, and full group-budget lists appeared in earlier mockup suggestions. Do not build them automatically or expose sensitive data merely because a mockup included them.

### Card and result content

Use title, category, location, event/visit time, supplied cost information, travel information, and “Why this fits.” Include official links and relevant verification caveats; use images only with appropriate rights and attribution.

The earlier “Ramen + Arcade,” exact spend, travel minutes, and group-fit percentages were illustrative mock content, not collected observations. A verified single activity is the recommended initial result; a multi-stop adventure requires separate timing, travel, availability, and cost validation.

### Required interface states

Support invalid/expired codes, room full or locked, duplicate/rejoining guests, missing intake, no overlapping availability, generation failure, incomplete provider data, zero candidates, disconnected voting, stale rounds, no consensus, and cancelled/changed matched events. Never leave the group in an endless loading or swiping loop.

## Modeling and data science

The initial decision engine is constrained filtering plus transparent ranking. It can demonstrate the product’s methodology without claiming a trained machine-learning system.

Inventory data describes available options. To fit a preference model, the team additionally needs real user/candidate exposures and real responses.

| Data type | Examples | Role |
|---|---|---|
| Candidate features | Category, price evidence, time, location, source quality | Describe options |
| Participant/group features | Interests, budget, availability, travel limit | Describe decision context |
| Derived features | Cost margin, route duration, overlap, worst-person burden | Fit and fairness signals |
| Preference observations | Yes/no votes on options actually shown | Potential learning labels |
| Decision outcomes | Match, explicit group selection | Evaluate group decisions |
| Follow-through | Booking-link click, self-reported attendance/satisfaction | Distinct downstream outcomes |

Do not treat unseen candidates as dislikes, missing votes as no, group non-selection as an individual negative, or booking clicks as actual bookings. Selection is not proof that an outing happened.

Before training, verify permitted model use for each source, define labels, obtain consent, assess sample size, and establish an evaluation split that avoids participant/room leakage. Compare against the rules baseline using preference accuracy, ranking utility, and worst-person feasibility/fairness; do not invent model-performance claims.

## Class deliverables and first collection

The project has been developed for a class pitch, requirements exercise, UI/UX planning, and a real-data collection assignment. The current assignment asks for a CSV or JSON containing at least a sample of collected data: approximately 2–3 manually collected observations or 10 publicly available observations.

It also asks for an image of a visualization made from that data, and explicitly says not to ask AI to generate graphs. Cursor may support collection and data preparation, but should not generate the assignment’s visualization or graph-generating code unless the instructor’s rule is explicitly changed.

Recommended first collection is at least 10 actual NYC Parks event records, saved with source identifiers, links, collection time, selected filters, and missing-field notes. The dataset offers a practical candidate-schema test with upcoming event dates and locations ([NYC Parks dataset](https://data.cityofnewyork.us/City-Government/NYC-Parks-Public-Events-Upcoming-14-Days/w3wp-dpdi)).

The student can then independently build a simple category-count or event-date chart in Excel or Tableau. A small sample demonstrates that collection works; it is not a complete training dataset or evidence of citywide coverage.

For reproducibility, document method, date/time window, geography, transformations, timezone assumptions, and access failures. Do not submit fictional fixtures as real collected observations or expose private participant data in class files.

## Competitive positioning and feedback

The class deck used Cobble, Beli, and Fever as comparison references, with CrewCal raised in feedback. These names explain the project’s positioning discussion; this document is not a newly verified feature audit of those products.

The intended differentiation is to determine what works for the group before asking it to vote, rather than focusing only on discovery or a poll. Do not assert that competitors categorically lack comparable features without fresh verification.

| Feedback concern | Product response |
|---|---|
| Why open another app? | Join from the existing chat through a lightweight link; return the result to that chat |
| Is the model real or a static list? | Explain hard filtering, group ranking, source evidence, and later preference learning |
| What if no one matches? | Designed recovery, trade-offs, explicit edits, no silent override |
| Are hours and prices accurate? | Provenance, checks, missing-value handling, official booking confirmation |
| Is the location fair? | Consider each participant’s route and worst-case burden |
| Does budget include travel? | Start activity-only; separate travel and add total-budget mode when support is adequate |
| What about pop-ups and tech talks? | Layer public feeds with approved local calendars, submissions, and curation |
| What is the actual output? | One group-approved plan, not a vague recommendation list |

Positive classroom feedback supported the relatability of group indecision, room-code participation, swipe interaction, student-budget fit, and narrow MVP. It is qualitative feedback, not evidence of paying demand, retention, or market validation.

## Success metrics

Measure a baseline before treating aspirational targets as commitments. Product success is a useful group decision and follow-through, not the raw number of swipes.

| Metric | Suggested definition |
|---|---|
| Join conversion | Unique invited people who join, only if a valid invite denominator is measurable |
| Preference completion | Joined participants who submit sufficient valid intake |
| Activation | Rooms that reach a generated deck with a defined active cohort |
| Time to decision | Report both room-created-to-match and round-start-to-match; include unsuccessful rooms separately |
| Match rate | Unanimously matched eligible rooms / eligible voting rooms |
| Recovery success | No-match rooms reaching a match after revision |
| Hard-constraint violation | Verified recommendations or plans later shown to violate a recorded hard limit |
| Unknown/stale rate | Candidate facts or plans requiring review or failing refresh |
| Handoff engagement | Directions, official booking, registration, and share actions |
| Repeat use | Organizers creating another room in an agreed observation window |
| Follow-through | Separately consented reports of actual outing completion or satisfaction |

Recommended safety target is zero known silently violated hard constraints. Speed and conversion targets require a pilot baseline; do not report invented numbers.

Suggested minimal events are `room_created`, `participant_joined`, `preferences_submitted`, `deck_generated`, `candidate_shown`, `vote_submitted`, `match_created`, `no_match_shown`, `preferences_revised`, `official_link_opened`, and `plan_shared`. Keep analytics pseudonymous and avoid sensitive payloads.

## Roadmap and implementation order

This is a proposed dependency-based sequence, not a team-approved calendar. Do not attach invented deadlines or claim tasks are complete.

### Collection and domain foundation

Inspect the repository and validate at least one real data path. Define candidate normalization, source permissions, participant intake, constraint outcomes, and a reproducible public-data sample.

### Core room vertical slice

Implement create/join, guest sessions, readiness, private intake, a fixed versioned deck, yes/no voting, unanimous matching, and the final shared plan. Use labeled fixtures where needed while retaining a real import path.

### Feasibility and recovery

Add time/budget/status filtering, supported travel evaluation, explainable ranking, privacy-safe no-match behavior, controlled revisions, and multi-user race/refresh tests.

### Supply and travel expansion

Add additional official adapters and approved local supply after access review. Introduce route integration and transport-cost mode only with truthful evidence and uncertainty handling.

### Pilot and learning

Run consented real sessions, inspect decision speed and failures, and collect actual exposures/votes. Consider learned ranking only after the baseline works and enough authorized data exists.

## Acceptance criteria and tests

These are recommended acceptance criteria for the implementation. They should be adapted to the final approved policies without weakening the privacy and hard-constraint guarantees.

| Area | Given / when / then |
|---|---|
| Guest join | Given a valid open room, when a friend follows its link, then they can join through the lightweight guest flow without a mandatory full account. |
| Invalid code | Given an invalid or expired code, when submitted, then a clear error appears without exposing room or participant data. |
| Room isolation | Given a participant in room A, when requesting room B’s private resources, then access is denied. |
| Budget | Given a hard cap and a confirmed admission cost above it, when evaluating the candidate, then it fails normal feasibility. |
| Price range | Given a range whose upper bound exceeds the cap, when evaluating it, then the low end alone cannot certify budget fit. |
| Unknown price | Given no price evidence, when evaluating a hard-budget user, then the candidate is unknown/review-required, not free or verified affordable. |
| Time overlap | Given no common availability, when generating a deck, then the app explains the conflict and offers revisions rather than inventing a shared time. |
| Event time | Given a fixed event outside the valid shared window, when evaluating it, then it fails the configured attendance policy. |
| Travel | Given a low average but one confirmed route above that participant’s cap, when evaluating the option, then it fails that hard limit. |
| Unsupported fact | Given missing accessibility/capacity evidence, when displaying the card, then the app does not claim the corresponding requirement is verified. |
| Private votes | Given participants casting votes, when another participant or organizer reads room state, then individual choices are not disclosed under the default privacy policy. |
| Pending vote | Given a missing vote, when checking unanimity, then it remains pending and cannot create a match. |
| Unanimity | Given every active cohort member votes yes, when processing the final vote, then exactly one matched result is persisted and shared. |
| Race/retry | Given duplicate requests or simultaneous completions, when processed, then unique vote and atomic match rules prevent duplicate results. |
| Late join | Given an active round, when a new guest joins, then the cohort is not silently changed and policy is communicated. |
| Revision | Given changed preferences or candidate facts, when starting another deck, then stale-round votes are not reused as current approval. |
| No consensus | Given completed voting without unanimity, when showing recovery, then nearest suggestions are not labeled as a mutual match. |
| Hard relaxation | Given a participant’s hard cap, when an organizer attempts to raise it, then the change requires that participant’s explicit approval. |
| Provider failure | Given a source timeout, when generation runs, then the app shows appropriate coverage/error information and never fabricates a successful fetch. |
| Cancellation | Given a known cancelled event, when revalidation occurs, then it is excluded or the existing plan is marked changed and requires review. |
| Demo labeling | Given fixture-backed data, when rendered, then it is clearly distinguishable from real collected or live data. |
| Accessibility | Given a keyboard or non-gesture user, when voting, then labeled button controls allow the same operation as swiping. |

Test pure decision logic, adapter normalization, authorization, concurrent voting, and full multi-session flows. Include timezone/daylight-saving boundaries, duplicate recurring events, one participant with a restrictive cap, missing source fields, and disconnected guests.

## Business model and boundaries

No revenue model has been confirmed. The initial business objective is to prove that groups join, decide, use the handoff, and return.

Affiliate links, local merchant partnerships, labeled sponsored placements, premium organizer tools, and community distribution were explored as later possibilities. Any sponsorship must remain disclosed and cannot bypass feasibility, privacy, or fair-ranking requirements.

Do not implement charging, commercial placements, referral attribution, or merchant promises from this document alone. Those require separate product and contractual decisions.

## Open questions and decision register

Record answers as the owner makes decisions. Distinguish a blocking decision from a detail that can remain configurable.

| Question | Status / impact | Suggested owner |
|---|---|---|
| What repository and framework already exist? | Blocking before stack changes | Project owner / engineering |
| Is responsive web the initial platform? | Confirm before platform-specific work | Project owner |
| Which first source is actually accessible? | Blocking for real-data ingestion | Data lead |
| What NYC neighborhoods/categories launch first? | Supply-scoping decision | Product + data |
| Are 3–8 participants the supported limits? | Confirm before enforcing limits | Product |
| What is the exact match rule? | Recommended unanimous yes; confirm before shipping | Product |
| What happens to late joiners, absent voters, and leavers? | Blocking for reliable round behavior | Product + engineering |
| Which input fields and aggregates may the organizer see? | Blocking before exposing room state | Product/privacy |
| How should unknown prices, hours, routes, and capacity be handled? | Blocking before claiming verified fit | Product + data |
| Is an output one activity or multiple stops? | Default one activity; confirm before itinerary work | Product |
| Does budget cover activity only or total spend? | Default activity-only with travel separate | Product |
| What supported hard needs have adequate evidence? | Confirm before adding corresponding filters | Product + data |
| How long are rooms and private data retained? | Define before a public pilot | Product/privacy |
| What source refresh/retention policies are permitted? | Source-specific review required | Data lead |
| Is a trained model required for the course deliverable? | Clarify with instructor if necessary | Team |
| What is the actual pilot baseline and success target? | Unknown until measured | Product/research |

## Cursor implementation guardrails

Before acting, distinguish a request for planning from a request for changes. For implementation requests, build a complete testable slice rather than stopping at an architecture proposal.

- **Preserve scope:** Prioritize room → intake → feasible deck → private vote → match/fallback → plan handoff.
- **Respect existing code:** Inspect before selecting dependencies or replacing components.
- **Keep evidence truthful:** Never invent event facts, route durations, fares, fit probabilities, or source checks.
- **Protect constraints:** Hard needs require explicit owner-controlled changes; no averaging away individual violations.
- **Protect privacy:** Do not expose database rows, individual votes, budgets, precise origins, or sensitive reasons.
- **Separate states:** Group approval, verified source facts, booked inventory, and actual attendance are different.
- **Make uncertainty visible:** Unknown is a first-class state, not an error to hide with plausible filler.
- **Use permitted data:** Review source terms before storage, redistribution, extraction, or model training.
- **Avoid unnecessary AI:** The MVP can use deterministic filtering, scoring, and explanation templates.
- **Test multi-user behavior:** Verify concurrent sessions, retries, cohort changes, versioning, and disconnections.
- **Document decisions:** Mark defaults as defaults until approved and update this brief when decisions change.
- **Respect the assignment:** Do not AI-generate the required graph; use real collected records rather than fixtures.

The simplest faithful product is a lightweight shared room that helps friends choose from activities that already fit. Everything else should earn its place by reducing coordination effort, improving decision speed or fairness, or making the chosen plan easier to act on.

