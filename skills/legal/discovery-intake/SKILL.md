---
name: legal-discovery-intake
description: "Plaintiff FELA/PI discovery intake workflow."
version: 1.0.0
author: ahfullerjd (with Hermes Agent)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [legal, discovery, intake, fela, personal-injury, plaintiff]
    category: legal
    related_skills: [legal-discovery-review]
---

# Legal Discovery Intake Skill

Plaintiff-side legal discovery intake workflow for FELA (Federal Employers' Liability Act) and
personal-injury litigation. Produces a structured intake package from client interview facts.
Does NOT perform document review, generate legal conclusions, or communicate with clients.

**CONFIDENTIALITY:** All intake materials are attorney work product. Work in a local directory
isolated from cloud storage. Never transmit client facts through external APIs without attorney
authorization. This skill uses synthetic facts for development and testing only.

**ATTORNEY REVIEW REQUIRED:** All outputs are drafts for attorney review. No output is a legal
conclusion. Language: "evidence supports / suggests / contradicts / requires attorney review."

## When to Use

Load this skill when an attorney or legal professional needs to:
- Structure a new client intake for a FELA or personal-injury matter
- Generate a comprehensive intake questionnaire from initial facts
- Produce a matter profile, issue checklist, and initial discovery plan
- Identify missing information and follow-up questions from initial client interview notes

## Prerequisites

- FELA and PI domain knowledge encoded in the agent
- `read_file` and `write_file` for intake note processing and output
- `terminal` for Python-based data structuring when needed
- Synthetic test fixtures at `skills/legal/discovery-intake/fixtures/` for validation (no real
  client data)

## How to Run

1. Load initial intake facts (from attorney notes, client questionnaire, or synthetic fixtures)
   using `read_file`.
2. Follow the Procedure below to produce each output section.
3. Write the complete intake package with `write_file` to a local matter directory.
4. Run the validation checklist at the end before presenting to the attorney.

## Quick Reference

| Output Section | Description |
|---------------|-------------|
| Matter Profile | Case identifier, court, filing date, statute of limitations |
| Parties / Witnesses / Entities | All persons and entities with roles and contact metadata |
| Incident Summary | Narrative summary of the incident in chronological order |
| FELA / PI Issue Checklist | Issues relevant to FELA negligence or PI tort theories |
| Injury / Medical-Treatment Capture | Injuries, diagnoses, treating providers, treatment timeline |
| Employment / Wage-Loss Capture | Job details, earnings, wage-loss period, occupational limits |
| Liability Theory Checklist | Negligence theories, statutes violated, evidence sources |
| Preservation / Spoliation Checklist | Documents to preserve, custodians, hold-letter targets |
| Missing-Information List | Gaps in the record that require further investigation |
| Client Interview Follow-Up Questions | Specific questions to ask the client at next meeting |
| Initial Discovery Plan | Phased discovery strategy with custodian and topic priorities |
| Draft Discovery Starter Sets | Sample RFPs, interrogatories, and RFAs |

## Procedure

### Step 1: Read and Structure Intake Facts

Load the intake facts file. Extract structured data:

```
- Client full name (synthetic-only for development)
- Date of incident
- Location of incident (terminal, yard, track, crossing, facility)
- Employer name and entity type
- Job craft and crew role
- Description of incident in client's own words
- Injuries claimed
- Medical treatment sought (providers, dates)
- Wage loss claimed (pre-injury earnings, return-to-work status)
- Witnesses identified
- Documents in client's possession
```

### Step 2: Produce Matter Profile

```
Case Identifier: [matter number or placeholder]
Court / Venue: [jurisdiction, if known]
Incident Date: [date]
Incident Location: [terminal, yard, track, crossing, facility — be specific: milepost, track designation, yard name]
SOL Issue Flag: [flag that a limitations deadline must be determined — do NOT
  compute or assert a date. Record the attorney-provided deadline here only
  after the attorney supplies it. This skill does not calculate limitations
  periods; that is a legal determination requiring attorney review.]
Case Type: FELA / PI / Both
Referral Source: [attorney / firm reference]
```

### Step 3: Build Parties / Witnesses / Entities Table

For each person or entity:
- Full name (synthetic only for testing)
- Role: plaintiff, defendant, witness, employer, medical provider, expert
- Contact status: known / unknown / represented
- Relevance summary (1-2 sentences)
- Evidence suggests / requires attorney review

### Step 4: Write Incident Summary

Chronological narrative. Include:
- Pre-incident context (job assignment, crew, equipment, weather, lighting)
- Incident mechanics (what happened, sequence of events)
- Post-incident response (first aid, ambulance, hospital, reporting)
- DO NOT include legal conclusions — describe facts

### Step 5: Complete FELA / PI Issue Checklist

For FELA cases, flag each applicable issue:

```
[ ] Unsafe work method / workplace
[ ] Negligent assignment (task beyond training or physical capacity)
[ ] Failure to provide adequate help / crew size
[ ] Failure to inspect workplace
[ ] Failure to promulgate or enforce safety rules
[ ] Negligent training or supervision
[ ] Violation of safety statute (FSAA, SAA, LBIA, FRSA)
[ ] Hours of service violation (fatigue)
[ ] Defective equipment / tools / machinery
[ ] Failure to warn of hazardous condition
[ ] Prior similar incidents / notice to employer
[ ] Retaliation or intimidation (FRSA)
[ ] Medical negligence in company-directed treatment
[ ] Other (describe): ___
```

For general PI cases, flag:

```
[ ] Premises liability (slip/fall, unsafe condition)
[ ] Motor vehicle negligence
[ ] Product liability
[ ] Medical malpractice
[ ] Other (describe): ___
```

Each checked item needs: brief factual basis, evidence sources to pursue, and strength
assessment (evidence supports / suggests / requires investigation).


All FELA and PI issue classifications above require attorney review against
the applicable statutory framework (45 U.S.C. sections 51-60 for FELA claims;
state tort law for PI claims). Issue flags are preliminary attorney-review
markers only.

### Step 6: Capture Injury and Medical Treatment

For each injury:
- Body part / system affected
- Diagnosis (if known)
- Treating provider (synthetic name only for testing)
- First treatment date
- Ongoing treatment status
- Surgical intervention (yes / no / unknown)
- Permanent restrictions (if any)
- Future medical needs (if known)

Separate section for medical causation facts:
- Pre-existing conditions
- Mechanism of injury linking to claimed condition
- Gaps in medical record requiring attorney review

### Step 7: Capture Employment and Wage Loss

For FELA cases, include railroad-specific fields:

```
- Locomotive Number / Consist: [engine number, consist configuration, car type]
- Equipment Involved: [specific tools, machinery, rolling stock, track appliances involved in incident]
- Railroad Employer: [synthetic name — e.g., Test Valley Railroad]
Job Craft: [e.g., freight conductor, track laborer, engineer, carman]
Crew / Gang: [crew identifier, if known]
Seniority Date: [date]
Pre-Injury Rate of Pay: [hourly / daily / monthly rate]
Average Monthly Earnings (12 months pre-injury): [amount — synthetic]
Date Last Worked: [date]
Return-to-Work Status: [not returned / light duty / full duty / unknown]
Occupational Limits: [physical restrictions affecting railroad work]
Lost Wages to Date: [approximate — synthetic]
Future Earning Capacity Impact: [summary — synthetic]
FELA Tax Offset Note: RRTA Tier I / Tier II tax treatment differs from FICA.
  Future lost earnings projections must use net-after-RRTA methodology.
```

### Step 8: Build Liability Theory Checklist

Map each negligence theory to:
- Elements for attorney to verify against governing authority (do NOT assert
  the legal elements as settled; flag them for attorney confirmation and cite
  the source the attorney provides)
- Supporting facts from intake
- Evidence sources (documents, witnesses, regulations, inspection records)
- Gaps requiring discovery
- Preliminary strength assessment (evidence supports / suggests / requires
  investigation — never a legal conclusion)

Every legal-standard entry in this checklist requires an attorney-provided or
source-cited authority. The agent does not supply the governing law; it records
the attorney's citation and flags any element lacking a confirmed source for
attorney review.

Include FELA-specific theories:
- 45 U.S.C. § 51 (general negligence — "featherweight" causation)
- 45 U.S.C. § 53 (contributory negligence — not a bar, reduces damages)
- Federal Safety Appliance Act (49 U.S.C. §§ 20301-20306) — strict liability
- Locomotive Inspection Act (49 U.S.C. §§ 20701-20703)
- Federal Railroad Safety Act (49 U.S.C. § 20109)
- Hours of Service Act (49 U.S.C. §§ 21101-21109)

### Step 9: Build Preservation / Spoliation Checklist

```
Documents / Evidence to Preserve:
[ ] Accident / incident reports (railroad internal, FRA)
[ ] dispatch records and train sheets
[ ] Track inspection reports
[ ] Equipment inspection and maintenance records
[ ] Employee training records
[ ] Rule violation history (employee and location)
[ ] Prior incident reports (same location / equipment / supervisor)
[ ] Surveillance video (yard cameras, locomotive cameras)
[ ] Radio / communication recordings
[ ] Crew time slips and payroll records
[ ] Medical records (railroad-provided and private)
[ ] Witness statements (formal and informal)
[ ] Photographs / video of scene and equipment
[ ] Discipline records (client and involved coworkers)

Hold Letter Targets:
[ ] Railroad claims department
[ ] Railroad safety department
[ ] Railroad IT (electronic records)
[ ] Medical providers and facilities
[ ] Union (if applicable)
```

### Step 10: List Missing Information

Items that are unknown or incomplete after initial intake:
- Factual gaps (what happened, who saw it, what equipment)
- Medical gaps (diagnoses, providers, treatment dates, prior conditions)
- Employment gaps (exact earnings, return-to-work status, RRB records)
- Witness gaps (unidentified witnesses, contact information)
- Document gaps (client doesn't have but employer likely possesses)

### Step 11: Generate Client Interview Follow-Up Questions

Specific, non-leading questions organized by topic:
- Incident details
- Medical treatment and current condition
- Employment and wage loss
- Witnesses and evidence
- Prior complaints, injuries, or discipline
- Post-incident communications with employer

### Step 12: Produce Initial Discovery Plan

Three phases:
- **Phase 1 (Preservation + Core Documents):** Hold letters, incident reports, personnel file,
  medical records, payroll records, dispatch records, track/equipment inspection records
- **Phase 2 (Liability Development):** Prior incidents, rule violations, training records,
  supervisor personnel files, FRA inspection reports, safety meeting minutes, crew statements,
  expert inspections
- **Phase 3 (Damages + Expert Discovery):** Economic expert data, medical expert review,
  surveillance / social media (if relevant), rehabilitation records, vocational assessment

### Step 13: Draft Discovery Starter Sets

**Requests for Production (Sample):**
1. All accident / incident reports concerning the [date] incident at [location].
2. All track inspection reports for [location] for the [period] preceding the incident.
3. All maintenance and inspection records for [equipment] for the [period].
4. All employee rule violation records for [location / supervisor / crew] for the [period].
5. All prior incident reports involving [location / equipment / supervisor] for the [period].
6. Complete personnel file for [client name — synthetic only].
7. All payroll and time-slip records for [client name] for the [period].
8. All surveillance video from [location / equipment] for the [date].
9. All training records for [client name] and [involved coworkers].
10. All FRA inspection reports for [location] for the [period].

**Interrogatories (Sample Topics):**
1. Identify all persons with knowledge of the incident or its investigation.
2. Describe all safety rules applicable to the task being performed.
3. Identify all prior similar incidents at [location] or involving [equipment].
4. Describe all inspections of [location / equipment] in the [period] before the incident.
5. Identify all documents relating to the incident or the plaintiff's employment.
6. Describe any disciplinary action taken against any employee as a result of the incident.
7. State whether any safety rule violation by the plaintiff is alleged.

**Requests for Admission (Sample Topics):**
1. Admit that [employer] was a common carrier by railroad engaged in interstate commerce.
2. Admit that [client] was employed by [employer] on [date].
3. Admit that [client] was acting within the scope of employment at the time of the incident.
4. Admit the authenticity of [key documents].

## Verification

Before presenting to the attorney:
- [ ] All sections completed with available information
- [ ] Missing-information list matches gaps in other sections
- [ ] No legal conclusions in narrative sections
- [ ] Synthetic-facts validation (development/testing only) — no real client data
- [ ] Attorney-review markers on all analysis sections
- [ ] FELA-specific fields completed (railroad employer, job craft, terminal/location, equipment)
- [ ] Preservation list covers all identified evidence sources
- [ ] Discovery plan aligned with liability theories
- [ ] FELA featherweight causation standard noted in liability section
- [ ] RRTA tax treatment noted in wage-loss section

## Pitfalls

- DO NOT assume client facts are complete — the missing-information list IS the product
- DO NOT draft discovery directed to the client — discovery targets the defendant and third parties
- DO NOT use "proves," "establishes," or "demonstrates" — use "evidence supports," "evidence
  suggests," "requires attorney review"
- FELA causation is "featherweight" — defendant's negligence need only play any part, even
  the slightest, in causing the injury. This is NOT general tort causation.
- Assumption of risk is NOT a defense in FELA (45 U.S.C. § 54)
- Contributory negligence reduces damages in FELA, does not bar recovery (45 U.S.C. § 53)
- Safety Appliance Act and Locomotive Inspection Act claims are strict liability — no need
  to prove negligence
