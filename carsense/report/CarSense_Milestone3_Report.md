---
title: "CarSense: A Multimedia Expert System for Diagnosing Car Problems by Sound"
subtitle: "CIS 4930 Multimedia Expert Systems, Milestone 3: Implementation and Testing"
author:
  - Dipak Mehta (Team Leader)
  - Edib Music
  - Kush Patel
  - Samir Patel
  - Sheehan Rahman
date: "December 2, 2026"
---

**University of Florida**

**Domain expert:** Himal Patel (auto mechanic)

**Demo video:** [Edib: unlisted YouTube link]

**Source code:** [Dipak: repository link]

# Implementation Details

## System Overview

[Dipak: two or three sentences on what CarSense does and how the seven modules fit together. Point to Figure 1 and Table 1.]

[Dipak: Figure 1, architecture diagram of the seven modules and the data passed between them. Save as `figures/fig1_architecture.png` and replace this line with `![](figures/fig1_architecture.png)`.]

*Figure 1. CarSense architecture.*

Table: Table 1. Modules and classes.

| Module | Class | Responsibility | Owner |
|---|---|---|---|
| User Interface | (TypeScript) | [UI owner] | [name] |
| Session Controller | `SessionController` | [Controller owner] | [name] |
| Audio Analyzer | `AudioClip`, `AudioAnalyzer` | [Audio owner] | [name] |
| Audio Matcher | `AudioMatcher` | [Audio owner] | [name] |
| Knowledge Base | `KnowledgeBase` | Loads and cross-checks the rule, part and question files | Samir Patel |
| Knowledge Base | `Part` | One car part with its name, cost level and media | Samir Patel, [KB owner] |
| Inference Engine | `Fact` | One immutable piece of evidence from the user or the audio matcher | Samir Patel |
| Inference Engine | `WorkingMemory` | All facts for one session; several values per name | Samir Patel |
| Inference Engine | `Rule` | One diagnostic rule; reports matched and missing conditions | Samir Patel |
| Inference Engine | `InferenceEngine` | Matches rules, applies meta-rules M1 to M3, ranks results | Samir Patel |
| Inference Engine | `Diagnosis` | One ranked result with confidence and its reasoning trace | Samir Patel |
| Explanation Module | `ExplanationBuilder` | [Explanation owner] | [name] |

## Languages, Libraries and Frameworks

Table: Table 2. Languages, libraries and tools.

| Part of the system | Language or tool | Version | Used for |
|---|---|---|---|
| Reasoning core and knowledge base loader | Python, standard library only | 3.11 | Facts, rules, inference, validation |
| Backend tests | pytest | 8.3.3 | Unit and integration tests |
| Session Controller | Flask | [Controller owner] | HTTP API between the UI and the backend |
| Audio Analyzer and Matcher | [Audio owner] | [version] | Pitch, loudness and repetition rate |
| User Interface | TypeScript with Vite | [UI owner] | Question, recording and results screens |
| Reference clip preparation | ffmpeg | 9.0 | Trimming and converting clips to 16 kHz mono WAV |
| Report | pandoc | 3.x | Building this document from Markdown |

## User Interface

[UI owner: the screens and how the user moves through them, how reference clips are played, how recording and upload work. Figure 4 goes here; Figure 5 can go here or in Section 2.3.]

[UI owner: Figure 4, question screen. Save as `screenshots/fig4_questions.png`.]

*Figure 4. Question screen.*

## Session Controller

[Controller owner: the Flask endpoints, the request and response format, and how a request becomes a `WorkingMemory`, an engine run and an explanation. A short code snippet of the main endpoint works well here.]

## Audio Analyzer and Matcher

[Audio owner: how dominant pitch, loudness and repetition rate are extracted, how a recording is compared with the 27 reference clips, and how the similarity score is computed. Include a snippet of the key function.]

## Knowledge Base

[KB owner: what is in `rules.json`, `parts.json` and `questions.json`, how the part images, videos and cost ranges were chosen, and how Himal Patel reviewed the rules. The loader class is described in Section 1.7.]

## Inference Engine and Core Classes

*Author: Samir Patel*

The reasoning core is written in Python 3.11 using only the standard library, so every other module can import it without extra setup. It has seven classes (Table 1). A `Fact` is a small immutable record of a name, a value and a source, where the source is either the user or the audio matcher; audio facts also carry a similarity score between 0 and 1. `WorkingMemory` holds the facts for one session and allows several values under one name, which the multi-select questions (timing and symptoms) need. The Session Controller builds it with one call, `WorkingMemory.from_answers(answers, audio)`. `KnowledgeBase` loads the three JSON files at startup and cross-checks them: every rule's part must exist, every condition value must be a real answer option in `questions.json`, and no IDs may repeat. A typo in the knowledge base stops the server with a message naming the rule, instead of producing a rule that silently never fires.

Each rule is one JSON object (Figure 2). Conditions come in three types: `is` (the fact has this value), `any` (it has at least one of these values) and `not` (it does not have this value). R8 uses all three, and its `not` condition on a sweet smell is what separates a vacuum leak (R8) from a coolant leak (R7). `Rule` also reports which conditions matched and which are missing, which the Explanation Module uses to say why a rule fired or almost fired.

```json
{
  "id": "R8",
  "sound_type": "hissing",
  "certainty": 0.70,
  "conditions": [
    {"fact": "sound", "is": "hissing"},
    {"fact": "location", "any": ["engine_bay", "engine_top", "engine_lower"]},
    {"fact": "symptom", "is": "rough_idle"},
    {"fact": "symptom", "not": "sweet_smell"}
  ],
  "conclusion": {"problem": "Vacuum leak", "part_id": "vacuum_hose",
                 "urgency": "Medium", "safe": "Yes", "cost": "Low"}
}
```

*Figure 2. Rule R8 in `kb/rules.json`.*

The `InferenceEngine` performs single-pass, data-driven (forward) rule matching with conflict resolution by confidence (Figure 3). It checks every rule against working memory once. A rule whose conditions all hold fires with its certainty, which is 0.70 for all twelve rules. A rule that matches only partly scores match ratio × certainty × 0.6 and is kept as an alternative only if that reaches 0.30. The meta-rules then run in order. M2 compares the audio match with each result's sound type: when they agree, confidence rises by 0.25 × similarity, capped at 0.95; when the recording disagrees with the sound the user chose, the result gets a note and its confidence is unchanged, so the audio never overrides the user. The results are ranked by confidence, with ties broken by urgency. M1 puts a `STOP_DRIVING` warning first if any result is Critical, and M3 marks the outcome uncertain and adds `SEE_MECHANIC` when nothing fired or the top confidence is below 0.50. The thresholds are named constants on the class, so they can be tuned with the domain expert without touching the logic.

```python
def condition_holds(cond: dict[str, Any], wm: WorkingMemory) -> bool:
    name = cond["fact"]
    if "is" in cond:
        return wm.has(name, cond["is"])
    if "any" in cond:
        return not wm.values(name).isdisjoint(cond["any"])
    return not wm.has(name, cond["not"])

def run(self, wm: WorkingMemory) -> dict[str, Any]:
    diagnoses = self._evaluate(wm)
    self._apply_m2(diagnoses, wm)
    diagnoses = self._rank(diagnoses)
    warnings: list[str] = []
    self._apply_m1(diagnoses, warnings)
    uncertain = self._apply_m3(diagnoses, warnings)
    return {"diagnoses": diagnoses, "warnings": warnings, "uncertain": uncertain}
```

*Figure 3. Condition matching in `rule.py` and the main loop of `InferenceEngine.run`.*

**How facts, rules and meta-rules interact.** Every answer on the question screen, and the audio match if there is a recording, becomes a fact. Rules read only facts; they never read each other's conclusions, so there is no chaining, and with twelve independent rules one pass is enough. Meta-rules read only the rule results and the audio fact: M2 adjusts confidence, ranking orders the results, and M1 and M3 add warnings. Each `Diagnosis` keeps the conditions it matched, the ones it is missing, and a note from every meta-rule that changed it. The explanation on the results screen therefore comes straight from the engine's own trace rather than being reconstructed afterwards.

## Explanation Module

[Explanation owner: how `ExplanationBuilder` turns the matched and missing conditions and the meta-rule notes into plain-language text for the results screen. Include a short example of its output.]

## Multimedia Integration

[Team: how text (questions, explanations), images (part photos), video (repair videos), audio (reference clips and the user's recording) and rules come together on the results screen. Each `Diagnosis` carries a `part_id`, and the controller looks up that part's images, video and cost range in the knowledge base.]

# System Integration and Functionality

## Execution Flow

[Controller owner: walk through Figure 6 from input to output. The eight steps from the design are: (1) the user answers guided questions and listens to reference clips; (2) the user can upload or record the noise; (3) the recording is analyzed and matched to the closest reference sound; (4) answers and the audio match become facts; (5) the inference engine applies the rules; (6) the meta-rules rank the results and add warnings; (7) the results screen shows the diagnosis, part image and video, cost, safety advice and explanation; (8) the user can change answers and try again.]

[Controller owner: Figure 6, execution flow diagram. Save as `figures/fig6_flow.png`.]

*Figure 6. Execution flow from user input to results.*

## Data, Rules and Multimedia Interaction

[Controller owner: how a request moves between the UI, controller, audio modules, engine and explanation module. The "How facts, rules and meta-rules interact" paragraph in Section 1.7 can be reused or shortened here.]

## Example Runs

[Controller and UI owners: two or three complete runs, for example worn brake pads with a matching recording (R1 boosted by M2), rod knock (R5 with the Stop driving warning from M1), and an unclear hissing case (R8 as a partial match, flagged uncertain by M3). Show the results screen for at least one.]

[UI owner: Figure 5, results screen. Save as `screenshots/fig5_results.png`.]

*Figure 5. Results screen.*

## Known Limitations

- With every rule at certainty 0.70 and a partial factor of 0.6, a partial match needs at least 72% of its conditions to reach the 0.30 threshold. In practice only R8, which has four conditions, can appear as an alternative; a three-condition rule matching two of three scores 0.28 and is dropped.
- The engine does not chain rules, and all twelve rules share the same certainty instead of values tuned per rule by the expert.
- Only CC0 reference clips were used. Knocking and squealing are real recordings of those faults, but some clicking, ticking and grinding clips are stand-ins (for example a 12 V solenoid for a starter click, and engine idle for lifter tick) because no CC0 recording of the exact fault was available.
- [Audio owner: limitations of the audio features and matcher.]
- [UI and Controller owners: limitations of the interface and integration.]

# Testing and Evaluation

## Test Cases

[Testing owner: one or two sentences on the overall test strategy, then complete Table 3 with the rows for the other modules.]

The backend core has 188 pytest tests, all passing on Python 3.11.9. `test_engine.py` has one case per rule that checks the problem, urgency, safe-to-drive advice and cost, plus cases for each meta-rule, partial matches, ties, empty input and unknown answer values. It also compares the two sample responses in the team's API contract field by field, so the controller and UI are built against output the engine really produces.

Table: Table 3. Test cases.

| Test file | What it covers | Tests | Result |
|---|---|---|---|
| `test_fact.py` | Fact creation, immutability, source and similarity checks | 14 | Pass |
| `test_working_memory.py` | Multi-value facts, building from answers, audio match input | 17 | Pass |
| `test_rule.py` | `is`, `any` and `not` conditions, match ratio, malformed rules | 36 | Pass |
| `test_diagnosis.py`, `test_part.py` | Result and part objects, output format | 17 | Pass |
| `test_knowledge_base.py` | Real `kb/` files, every rule can fire, 18 kinds of bad data | 36 | Pass |
| `test_engine.py` | All 12 rules, M1 to M3, partials, ties, edge cases | 38 | Pass |
| `test_clips.py` | 27 reference clips: count, format, credits, license | 30 | Pass |
| [Audio owner] | [Audio Analyzer and Matcher] | [n] | [result] |
| [Controller owner] | [API endpoints] | [n] | [result] |
| [UI owner] | [UI tests or manual checklist] | [n] | [result] |

## Inference Output

Figure 7 is an excerpt of the engine test log; the full log is in `report/logs/engine_tests.txt`.

```
tests/test_engine.py::test_each_rule[R1] PASSED                [  2%]
tests/test_engine.py::test_each_rule[R5] PASSED                [ 13%]
tests/test_engine.py::test_each_rule[R12] PASSED               [ 31%]
tests/test_engine.py::test_m1_stop_driving_first PASSED        [ 36%]
tests/test_engine.py::test_m1_comes_before_m3 PASSED           [ 42%]
tests/test_engine.py::test_m2_boost PASSED                     [ 44%]
tests/test_engine.py::test_m2_cap PASSED                       [ 50%]
tests/test_engine.py::test_m2_disagreement PASSED              [ 55%]
tests/test_engine.py::test_m3_no_match PASSED                  [ 63%]
tests/test_engine.py::test_partial_listed_as_alternative PASSED [ 71%]
tests/test_engine.py::test_r7_vs_r8_by_symptoms PASSED         [ 76%]
tests/test_engine.py::test_core_api_example_2 PASSED           [100%]
============================= 38 passed in 0.11s ==============
```

*Figure 7. Excerpt of the inference engine test log.*

[Testing owner: add screenshots or logs from the other modules showing correct output.]

## Performance

[Testing owner: one sentence introducing Table 5, plus the rows for the other modules.]

The inference engine averages about 0.1 ms per diagnosis on a laptop (100 runs per scenario, each building working memory and calling `run()`), so reasoning adds no noticeable delay to a request. Loading and validating the knowledge base takes about 1 ms and happens once at startup. The full timing output is in `report/logs/engine_timing.txt`.

Table: Table 5. Performance timings.

| Operation | Average time | Notes |
|---|---|---|
| `InferenceEngine.run`, rule fires with audio match | 0.09 ms | R1 boosted by M2 |
| `InferenceEngine.run`, Critical result | 0.09 ms | R5 with Stop driving warning |
| `InferenceEngine.run`, fired plus partial | 0.09 ms | R7 fired, R8 partial |
| `InferenceEngine.run`, no match | 0.09 ms | Uncertain, see a mechanic |
| Knowledge base load and validate | 1.3 ms | Once at startup |
| [Audio owner: feature extraction for one recording] | [ms] | |
| [Audio owner: matching against 27 clips] | [ms] | |
| [Controller owner: full request, answers to response] | [ms] | |

## Audio Matching Accuracy

[Audio owner: Table 4, leave-one-out accuracy over the 27 reference clips (3 per sound type) and the confusion matrix. Comment on which sound types are confused and why.]

Table: Table 4. Audio matching accuracy (leave-one-out).

| Sound type | Correct | Total | Accuracy |
|---|---|---|---|
| [Audio owner] | | 3 | |

## Robustness and User Interaction

[Testing owner: behavior with bad or missing input (empty answers, no recording, a noisy recording), and feedback from any user trials, including Himal Patel's review of the reference clips.]

# Results

[Testing owner: summarize the results of Tables 3 to 5 in Table 6 and two or three sentences. Section 4 and Section 5 together are worth 10%.]

Table: Table 6. Summary of test results.

| Area | Tests or trials | Passed | Key number |
|---|---|---|---|
| Backend core (reasoning and knowledge base) | 188 | 188 | 0.1 ms per diagnosis |
| [Audio] | | | [accuracy] |
| [Controller and UI] | | | |

# Discussion and Improvements

## Strengths

[Team: for example, every diagnosis is explained from the engine's own trace; the knowledge base is checked at startup; audio supports the user's answers but never overrides them.]

## Weaknesses

[Team: draw on Section 2.4.]

## Next Steps

- Tune the certainty of each rule and the partial-match threshold with Himal Patel, so that more near matches appear as alternatives.
- Replace stand-in reference clips with real recordings of each fault, ideally recorded with Himal Patel on cars in his shop.
- [Team: further next steps toward a final system.]

# Appendix A: Code Listings {-}

[Team: key code listings. Samir: full `inference_engine.py` and `rule.py`. Other owners: their main classes.]

# Appendix B: Full Test Table {-}

[Testing owner: the full list of test cases for every module. The backend list can be copied from `report/logs/test_results.txt`.]

# Appendix C: Media Credits {-}

All reference clips come from Freesound and are released under CC0 1.0. Each is a 4 to 5 second excerpt of the owner's preview, converted to 16 kHz mono WAV and peak normalized.

| Clip | Owner | Original title | Freesound ID |
|---|---|---|---|
| squealing_1 | WavJunction.com | Car Brakes sqeak screech squeal stop.wav | 456764 |
| squealing_2 | timpet55 | Bus Stopping with squeaky brakes.wav | 706273 |
| squealing_3 | Star142857 | Car with Belt Squeeling.mp3 | 608747 |
| grinding_1 | stib | disc brake.wav | 494321 |
| grinding_2 | nissse | 1983 Volvo 245 starter engagement failure + successful start | 322974 |
| grinding_3 | Ev-Dawg | Metal Grinding Very Slow | 336001 |
| clicking_1 | shdwtek | 12 Volt Solenoid Clicks | 679204 |
| clicking_2 | tt_runscript | Contactor/motor overload relay noises | 807384 |
| clicking_3 | greatsoundstube | ignition turn car start.wav | 629313 |
| knocking_1 | jlstaples | engine-knock.aif | 535073 |
| knocking_2 | craigsmith | S41-23 Car bearing knocking; bad auto engine; loop.wav | 675725 |
| knocking_3 | craigsmith | S41-27 Bad car engine bearings clunking.wav | 675724 |
| ticking_1 | greatsoundstube | car engine under bonnet.wav | 628539 |
| ticking_2 | C-V | Diesel idle 2.wav | 565597 |
| ticking_3 | RichieMcMullen | engine_idle_loop_2.wav | 386792 |
| hissing_1 | henrikcederblad | FOL-gas-leak-01.wav | 615668 |
| hissing_2 | JohanHauskater | gas_leak_3_samples | 855703 |
| hissing_3 | brunoboselli | Air (or steam) pressure release | 457294 |
| humming_1 | ViveleVent | Tire noise on the highway | 817389 |
| humming_2 | gecop | Highway drive interior | 521766 |
| humming_3 | jc144940 | Car Interior Driving Down Road.aiff | 179121 |
| clunking_1 | Breviceps | Passing car + road bump | 508170 |
| clunking_2 | menfa | car_speedbump_tacoya_bar_y_taqueria | 837875 |
| clunking_3 | buddhafish | Interior Prius driving rough road w rattles.wav | 327718 |
| whining_1 | mickyman5000 | JCB_Hydraulic_Power_Steering.wav | 340686 |
| whining_2 | SoundsofTheMachine | Motors_Hydraulic_Handycap_Ramp | 784981 |
| whining_3 | buddhafish | Interior Prius drive w accelerate.wav | 327721 |

Each clip's page is at `https://freesound.org/s/<Freesound ID>/`.

[KB owner: credits for part images and videos.]
