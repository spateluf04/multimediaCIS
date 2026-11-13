# Core API

This is what the controller, audio, explanation and UI code can rely on from the reasoning core. If you need something changed here, talk to Samir first so the tests stay in sync.

## Facts

Every answer becomes a `Fact(name, value, source)`. `source` is `"user"` or `"audio"`. A name can hold more than one value (`timing`, `symptom`).

| Fact | Select | Values |
|---|---|---|
| `sound` | single | `squealing`, `grinding`, `clicking`, `knocking`, `ticking`, `hissing`, `humming`, `clunking`, `whining` |
| `timing` | multi | `braking`, `turning`, `steering`, `starting`, `accelerating`, `idling`, `over_bumps`, `with_engine_speed`, `with_vehicle_speed` |
| `location` | single | `wheels`, `engine_bay`, `engine_top`, `engine_lower`, `underneath` |
| `symptom` | multi | `sweet_smell`, `running_hot`, `rough_idle`, `wont_start`, `warning_light`, `vibration` |
| `audio_match` | system | one `sound` value, plus `similarity` in [0, 1] |

Notes:

- `knocking` is a deep knock, `ticking` is a light tick.
- `turning` means the car is turning; `steering` means turning the wheel (including when parked).
- Display text for every option lives in `kb/questions.json`. Use the IDs above in code, never the display text.

## Questions (`kb/questions.json`)

A list of questions in the order the UI should ask them. `id` is the fact name, and each option `id` is the value sent back in `answers`. `hint` is optional.

```json
{
  "id": "sound",
  "text": "What does the noise sound like?",
  "select": "single",
  "options": [
    {"id": "squealing", "label": "Squealing", "hint": "High-pitched squeal or screech"}
  ]
}
```

## Loading the knowledge base

```python
from carsense.knowledge.knowledge_base import KnowledgeBase

kb = KnowledgeBase.load("../kb")
```

`load` checks that the three files agree with each other (rule parts exist, every condition value is a real option, no duplicate IDs) and raises `ValueError` listing every problem it finds. `kb.part(part_id)` returns the `Part` for a diagnosis, and `kb.questions()` is what the UI renders.

## Building working memory

The controller passes the answers dict straight from the request, plus the audio match if there was a recording:

```python
from carsense.reasoning.working_memory import WorkingMemory

wm = WorkingMemory.from_answers(answers, audio)
```

`answers` uses the fact names as keys. Single-select values are strings, multi-select values are lists. Missing keys are fine.

```json
{
  "sound": "squealing",
  "timing": ["braking"],
  "location": "wheels",
  "symptom": []
}
```

`audio` is `None` when there is no recording. Otherwise the audio matcher returns:

```json
{"sound": "squealing", "similarity": 0.82}
```

## Rule format (`kb/rules.json`)

```json
{
  "id": "R3",
  "sound_type": "squealing",
  "certainty": 0.70,
  "conditions": [
    {"fact": "sound", "is": "squealing"},
    {"fact": "timing", "any": ["starting", "accelerating"]},
    {"fact": "location", "any": ["engine_bay", "engine_top", "engine_lower"]}
  ],
  "conclusion": {
    "problem": "Loose or worn drive belt",
    "part_id": "drive_belt",
    "urgency": "Medium",
    "safe": "Yes, for short trips",
    "cost": "Low"
  }
}
```

Condition types:

- `is`: the fact has exactly this value.
- `any`: the fact has at least one of these values.
- `not`: the fact does not have this value (R8 uses it for "no sweet smell").

`sound_type` is what the audio match is compared against. `part_id` must exist in `kb/parts.json`.

## Running the engine

```python
from carsense.reasoning.inference_engine import InferenceEngine

result = InferenceEngine(kb).run(wm)
```

The engine does one forward pass: it checks every rule against the facts, applies the meta-rules, and ranks the results by confidence. Rule conclusions do not feed other rules.

- Fired rule: confidence is the rule's `certainty`.
- Partial match: `match_ratio * certainty * 0.6`, kept only if at least 0.30.
- M2: if the audio match agrees with the rule's `sound_type`, add `0.25 * similarity`, capped at 0.95. If it disagrees with the user's sound, a note is added and confidence is unchanged.
- Ties are broken by urgency (Critical, High, Medium, Low).
- M1: any Critical result puts `STOP_DRIVING` first in `warnings`.
- M3: if nothing fired, or the top confidence is under 0.50, `uncertain` is true and `SEE_MECHANIC` is added.

## Output shape

`run()` returns a dict. `diagnoses` holds `Diagnosis` objects; call `to_dict()` on each before sending JSON. `matched` and `missing` are the rule's own condition dicts.

Example 1: squealing, braking, wheels, with a recording that matched squealing at 0.80. R1 fires and M2 boosts it.

```json
{
  "diagnoses": [
    {
      "rule_id": "R1",
      "problem": "Worn brake pads",
      "part_id": "brake_pads",
      "urgency": "Medium",
      "safe": "Yes, but repair soon",
      "cost": "Low",
      "confidence": 0.9,
      "kind": "fired",
      "matched": [
        {"fact": "sound", "is": "squealing"},
        {"fact": "timing", "is": "braking"},
        {"fact": "location", "is": "wheels"}
      ],
      "missing": [],
      "notes": ["M2: audio match (squealing, 0.80) agrees, confidence +0.20"]
    }
  ],
  "warnings": [],
  "uncertain": false
}
```

Example 2: hissing from the engine bay, no symptoms picked, no recording. Nothing fires. R8 matches 3 of 4 conditions (0.75 x 0.70 x 0.6 = 0.315), so it is kept as a partial, and M3 flags the result as uncertain.

```json
{
  "diagnoses": [
    {
      "rule_id": "R8",
      "problem": "Vacuum leak",
      "part_id": "vacuum_hose",
      "urgency": "Medium",
      "safe": "Yes",
      "cost": "Low",
      "confidence": 0.315,
      "kind": "partial",
      "matched": [
        {"fact": "sound", "is": "hissing"},
        {"fact": "location", "any": ["engine_bay", "engine_top", "engine_lower"]},
        {"fact": "symptom", "not": "sweet_smell"}
      ],
      "missing": [
        {"fact": "symptom", "is": "rough_idle"}
      ],
      "notes": []
    }
  ],
  "warnings": ["SEE_MECHANIC"],
  "uncertain": true
}
```

Warning codes the UI should handle: `STOP_DRIVING`, `SEE_MECHANIC`.
