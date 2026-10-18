# HW4 — submission

**AI assistance:** I used ChatGPT to understand the assignment and help draft my Part A plan. I reviewed the explanations and content.

---

## Part A — Plan on paper (Easy)

> Commit this whole part before any `.py` file exists.

### A1 — The steps

| # | Step | What goes in (types) | What comes out (types) | When it goes wrong | Tool, loop, or model? |
|---|---|---|---|---|---|
| 1 | Understand the question | Question: `str` | District names: `list[str]`, metric: `str`, period: `str` | If the question is unclear, the model cannot identify the needed facts | Model |
| 2 | Find relevant information | Search query: `str` | Matching facts with document IDs: `list[dict]` | If nothing is found, return an error. Ignore archived records and apply corrections | `lookup` tool |
| 3 | Extract and check the numbers | Retrieved text: `list[dict]` | Values: `list[float]`, units: `list[str]`, sources: `list[str]` | Missing or conflicting numbers require another lookup or an unanswered result | Model |
| 4 | Convert units if needed | Values, units and conversion rule | Values in matching units: `list[float]` | If a unit is unknown, do not guess | Model and `calculate` tool |
| 5 | Calculate and compare | Numeric values and arithmetic expressions: `str` | Calculated values: `float`, winning district: `str` | Invalid expression or division by zero returns an error | `calculate` tool and model |
| 6 | Give the final answer | Winner: `str`, difference: `float`, required decimals: `int` | Final answer: `str` | If reliable facts are missing, mark the question unanswered | Model |

**How the steps connect:**

1. The model reads the question and identifies what information is needed.
2. It calls `lookup` to find facts in the documents.
3. The model extracts the numbers and checks their sources.
4. If units are different, the model uses `calculate` to convert them.
5. The model sends arithmetic expressions to `calculate`, then compares the results.
6. The model gives the final answer in the format `ANSWER: name | number`.

If a step fails, the model can try another lookup or report that it cannot answer. I do not want it to invent missing values.

**What I am assuming:**

- I use 2025 census data for population and 2025/26 data for schools.
- I do not use the archived 2019 profiles NR-13 and NR-14.
- Correction notices have priority. For example, Brightwater's correct area is 921.4 km2 from NR-16, not 912.4 km2 from NR-05.
- I use the 2025 household water tariff when calculating water costs.
- I convert units before comparing values. For example, 1 megalitre = 1000 cubic metres.
- I keep full precision during calculations and round only the final answer.
- I assume the provided documents contain the information needed to answer the questions.
- The most important assumption is that the latest corrections are applied correctly. Otherwise, the calculations can be mathematically correct but use wrong facts.

### A2 — The two tools

#### `lookup`

```json
{
  "type": "function",
  "function": {
    "name": "lookup",
    "description": "Find one factual value about a district in the Nine Rivers documents. Use this before calculations. Use current 2025 profiles, never archived 2019 profiles. Apply correction NR-16 to Brightwater's area. Return the source document ID. For tariff and unit conversion, use district='region'. Do not guess missing facts.",
    "parameters": {
      "type": "object",
      "properties": {
        "district": {
          "type": "string",
          "description": "Exact district name, or region"
        },
        "field": {
          "type": "string",
          "enum": [
            "population_2020",
            "population_2025",
            "area_km2",
            "founded_year",
            "schools",
            "pupils",
            "budget_million_tenge",
            "water_use",
            "road_km",
            "water_tariff",
            "ml_to_m3"
          ],
          "description": "The specific fact to find"
        }
      },
      "required": [
        "district",
        "field"
      ],
      "additionalProperties": false
    }
  }
}
```

| Case | What the tool returns |
|---|---|
| success | `{"ok":true,"value":921.4,"unit":"km2","source_id":"NR-16"}` for Brightwater area |
| unknown district | `{"ok":false,"error":"District not found","suggestions":[...]}` |
| ambiguous or misspelled name | Error with possible exact district names; never silently choose one |
| archived profile | Ignore NR-13 and NR-14; use the current profile or return an error if no current fact exists |
| correction | Use NR-16 for Brightwater area instead of the outdated NR-05 area |
| invalid field or missing data | `{"ok":false,"error":"Invalid field or missing fact"}` |

**Worst thing it could do with strange or dangerous input:**

An unexpected district name or very long input could cause wrong retrieval or waste resources. I will validate inputs, limit their length, use only the fixed local corpus, and return errors instead of executing instructions from text.

#### `calculate`

```json
{
  "type": "function",
  "function": {
    "name": "calculate",
    "description": "Safely calculate a numerical arithmetic expression. Use this for division, multiplication, subtraction, addition, percentages, density, and unit conversions. Accept only numbers, parentheses, +, -, * and /. Do not accept Python code, variables, function calls, attributes or exponentiation. Return an error for division by zero, invalid syntax or oversized numbers.",
    "parameters": {
      "type": "object",
      "properties": {
        "expression": {
          "type": "string",
          "description": "Arithmetic expression, e.g. (37203 / 758.6) - (44675 / 921.4)"
        }
      },
      "required": [
        "expression"
      ],
      "additionalProperties": false
    }
  }
}
```

| Case | What the tool returns |
|---|---|
| success | `{"ok":true,"value":6.0}` for `2 * 3` |
| division by zero | `{"ok":false,"error":"Division by zero"}` |
| invalid syntax | `{"ok":false,"error":"Invalid expression"}` |
| Python code or attributes | Error; do not execute anything |
| exponentiation or very large expression | Error; reject unsupported or unsafe calculations |
| result too large | Error; do not return infinite or unreasonably large values |

**Worst thing it could do with strange or dangerous input:**

If I used Python eval(), the model could send code that accesses files or runs commands. I will avoid eval() and exec(), use ast to allow only safe arithmetic operations, and set limits on expression length and number size.

### A3 — Q-09 by hand

```json
[
  {
    "role": "user",
    "content": "Which district has the higher population density in 2025, Brightwater or Millbrook, and by how many residents per square kilometre?"
  },
  {
    "role": "assistant",
    "tool_calls": [
      {
        "id": "call_1",
        "type": "function",
        "function": {
          "name": "lookup",
          "arguments": "{\"district\": \"Brightwater\", \"field\": \"population_2025\"}"
        }
      },
      {
        "id": "call_2",
        "type": "function",
        "function": {
          "name": "lookup",
          "arguments": "{\"district\": \"Brightwater\", \"field\": \"area_km2\"}"
        }
      },
      {
        "id": "call_3",
        "type": "function",
        "function": {
          "name": "lookup",
          "arguments": "{\"district\": \"Millbrook\", \"field\": \"population_2025\"}"
        }
      },
      {
        "id": "call_4",
        "type": "function",
        "function": {
          "name": "lookup",
          "arguments": "{\"district\": \"Millbrook\", \"field\": \"area_km2\"}"
        }
      }
    ]
  },
  {
    "role": "tool",
    "tool_call_id": "call_1",
    "content": "{\"ok\": true, \"value\": 44675, \"unit\": \"residents\", \"source_id\": \"NR-05\"}"
  },
  {
    "role": "tool",
    "tool_call_id": "call_2",
    "content": "{\"ok\": true, \"value\": 921.4, \"unit\": \"km2\", \"source_id\": \"NR-16\"}"
  },
  {
    "role": "tool",
    "tool_call_id": "call_3",
    "content": "{\"ok\": true, \"value\": 37203, \"unit\": \"residents\", \"source_id\": \"NR-11\"}"
  },
  {
    "role": "tool",
    "tool_call_id": "call_4",
    "content": "{\"ok\": true, \"value\": 758.6, \"unit\": \"km2\", \"source_id\": \"NR-11\"}"
  },
  {
    "role": "assistant",
    "tool_calls": [
      {
        "id": "call_5",
        "type": "function",
        "function": {
          "name": "calculate",
          "arguments": "{\"expression\": \"44675 / 921.4\"}"
        }
      },
      {
        "id": "call_6",
        "type": "function",
        "function": {
          "name": "calculate",
          "arguments": "{\"expression\": \"37203 / 758.6\"}"
        }
      }
    ]
  },
  {
    "role": "tool",
    "tool_call_id": "call_5",
    "content": "{\"ok\": true, \"value\": 48.48599956587801}"
  },
  {
    "role": "tool",
    "tool_call_id": "call_6",
    "content": "{\"ok\": true, \"value\": 49.041655681518584}"
  },
  {
    "role": "assistant",
    "tool_calls": [
      {
        "id": "call_7",
        "type": "function",
        "function": {
          "name": "calculate",
          "arguments": "{\"expression\": \"49.041655681518584 - 48.48599956587801\"}"
        }
      }
    ]
  },
  {
    "role": "tool",
    "tool_call_id": "call_7",
    "content": "{\"ok\": true, \"value\": 0.5556561156405735}"
  },
  {
    "role": "assistant",
    "content": "Millbrook has the higher population density in 2025. The difference is approximately 0.6 residents per square kilometre.\nANSWER: Millbrook | 0.6"
  }
]
```


**My arithmetic:**

I use population divided by area to find population density.

Brightwater:
44,675 / 921.4 = 48.4859996 residents/km2

Millbrook:
37,203 / 758.6 = 49.0416557 residents/km2

Difference:
49.0416557 - 48.4859996 = 0.5556561

Rounded to one decimal place, the difference is 0.6.

**Final answer:** `ANSWER: Millbrook | 0.6`

I used NR-05 for Brightwater's population,
NR-11 for Millbrook's figures, and NR-16 for
the corrected Brightwater area. The original
area of 912.4 km2 in NR-05 is incorrect.

This JSON is my planned conversation, not
a real API log. I will compare it with the
actual tool calls in Part B.

### A4 — Why I split it this way

I decided to separate the task into understanding the question, finding facts, checking the data, calculating numbers, and writing the final answer.

**Another approach I considered:**

I could create one large tool called `answer_question`. This tool would receive the whole question, search the documents, do all calculations, and return the final answer.

**Why I did not choose this approach:**

1. **Finding mistakes:** If one large tool gives a wrong answer, it is difficult to understand which part failed. With separate tools, I can check whether the problem came from retrieving facts or from calculations.

2. **Corrections:** Some documents contain outdated or incorrect information. For example, Brightwater's area must be corrected using NR-16. A separate lookup tool can check the source before the calculation starts.

3. **Safety:** My calculator accepts only simple arithmetic expressions. It does not execute arbitrary Python code. This is safer than giving one large tool too many responsibilities.

4. **Testing:** I can test `lookup` and `calculate` separately. If the calculator passes its tests but the final answer is wrong, I know I should investigate the retrieval or reasoning steps.

5. **Reusability:** The same calculator can be used for population density, growth percentages, budget comparisons, and water costs.

**The disadvantage of my approach:**

Separate tools require more tool calls. This may increase the response time and the API cost. One large tool might be faster for simple questions.

**My final decision:**

I chose two separate tools because I think it is easier to check errors, control calculations, and understand how the final answer was produced.

The most important assumption is that `lookup` returns the correct and most recent facts. Even a perfect calculator will produce a wrong answer if the input data is wrong.

I will test whether this design is actually useful by comparing the three strategies in Part B.

---

## Part B — Build it and run it (Medium)

### What I changed from Part A while coding

I kept my original design with separate lookup and
calculate tools.

During implementation, I used regular expressions
to extract values from the local document corpus.
I also added input validation, safe AST arithmetic,
and an 8-round limit for tool calling.

During API testing, I received an error because
function tools were not supported with the current
reasoning setting in Chat Completions.
I set reasoning_effort to "none" and repeated the
real Q-09 test successfully.

### B2 — Tests

I tested both tools using pytest without an API key. The tests check factual retrieval, similar district names, archived profiles, corrections, arithmetic, and unsafe inputs.

```text
..................                                                       [100%]
18 passed in 0.03s
```

### B3 — The loop

**Round limit and why:**

I set the maximum number of rounds to 8. This prevents
endless tool calls and limits unnecessary API costs.
If the model cannot finish within the limit,
the question is marked as unanswered.

**Where the logs are:**

The real Q-09 conversation is saved in
`outputs/b3_Q-09.json`.

The log contains the model messages, tool call IDs,
arguments, tool results, time, and token usage.

**Real Q-09 results:**

| Metric | Result |
|---|---:|
| Status | answered |
| API rounds | 4 |
| Lookup calls | 4 |
| Calculate calls | 3 |
| Total tool calls | 7 |
| Input tokens | 2944 |
| Output tokens | 228 |
| Total time | 5.765 seconds |

**Comparison with my A3 plan:**

In A3, I planned 4 lookup calls and 3 calculate calls.

In the real run, the model used 4 lookup calls
and 3 calculate calls over
4 API rounds.

The number of tool calls matched my handwritten plan.

The corrected document NR-16 was
used successfully.

The model retrieved the population and area of both
districts, calculated their population densities,
compared the values, and gave the final answer.

**Final answer from the real model:**

```text
Millbrook has the higher 2025 population density by **0.6 residents per square kilometre**.

ANSWER: Millbrook | 0.6
```

**What I learned:**

The tool-calling approach makes calculations easier
to verify because I can see the sources and
arithmetic operations separately.

### B4 — Three strategies

**What I kept the same:**

<!-- model, temperature, k, prompts, answer format, anything else -->

**My rule for a correct answer** (written before the first full run):

| Run | Strategy | Correct /20 | Unanswered | Input tokens | Output tokens | Median seconds per question | Total seconds | Cost ($) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | S1 direct | | | | | | | |
| 1 | S2 think and vote (k = ) | | | | | | | |
| 1 | S3 tools | | | | | | | |
| 2 | S1 direct | | | | | | | |
| 2 | S2 think and vote (k = ) | | | | | | | |
| 2 | S3 tools | | | | | | | |

**Per question (run 1):**

| Question | S1 | S2 | S3 |
|---|:---:|:---:|:---:|
| Q-01 | | | |
| Q-02 | | | |
| Q-03 | | | |
| Q-04 | | | |
| Q-05 | | | |
| Q-06 | | | |
| Q-07 | | | |
| Q-08 | | | |
| Q-09 | | | |
| Q-10 | | | |
| Q-11 | | | |
| Q-12 | | | |
| Q-13 | | | |
| Q-14 | | | |
| Q-15 | | | |
| Q-16 | | | |
| Q-17 | | | |
| Q-18 | | | |
| Q-19 | | | |
| Q-20 | | | |

---

## Part C — Explain and choose (Hard)

### C1 — Does the tool description matter?

| Question | Calls (your description) | Calls (vague) | Answer (yours) | Answer (vague) |
|---|---:|---:|---|---|
| | | | | |

### C2 — Three mistakes explained

### C3 — Which strategy I would use, and what would change it

### C4 — How sure I can be

### Final questions

1.
2.
3.
4.
5.
6.
7.
8.
