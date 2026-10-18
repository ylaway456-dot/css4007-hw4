# HW4 — submission

**AI assistance:** I used ChatGPT to help plan Part A, draft and debug Python code, design tests, and write explanations based on my experiment logs. I ran the experiments in Google Colab and checked the outputs and calculations.

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

- Model: `gpt-5.6-luna` for all strategies.
- The same 20 questions in the same order.
- The same source corpus for S1 and S2.
- The same final answer format: `ANSWER: name | number`.
- The same rounding requirement from each question.
- `reasoning_effort="none"` for API compatibility.
- S1 makes one direct request per question.
- S2 makes 5 independent requests and uses majority voting.
- S3 uses only lookup and calculate without documents
  in its prompt.
- S2 will use temperature 0.7 if supported by the model.
  Otherwise, I will record that temperature could not be set.
- Each experiment will be repeated twice.

**My rule for a correct answer** (written before the first full run):

1. The answer must contain `ANSWER: name | number`.
2. The name must match the reference answer
   (case-insensitive, without surrounding spaces).
3. The numerical result is compared with the reference value
   rounded to the required number of decimal places.
4. A difference of at most one unit in the last decimal
   place is allowed.
5. An invalid answer, missing answer, or API failure is
   counted as unanswered, not as correct.
6. For S2, I vote on the complete name-and-number pair.
   If there is a tie, I choose the earliest tied answer.
7. I use reference answers only for scoring after generation.
   I never send them to the model.

**Cost calculation:**

I will calculate costs from actual input/output token usage
and the applicable API prices. Failed calls without usage
are recorded separately.

| Run | Strategy | Correct /20 | Unanswered | Input tokens | Output tokens | Median seconds per question | Total seconds | Cost ($) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | S1 direct | 8/20 | 1 | 44140 | 1338 | 1.337 | 27.377 | $0.010434 |
| 1 | S2 think and vote (k = 5) | 14/20 | 0 | 222700 | 11085 | 7.524 | 155.767 | $0.057842 |
| 1 | S3 tools | 15/20 | 0 | 46738 | 4153 | 3.875 | 81.627 | $0.014331 |
| 2 | S1 direct | 8/20 | 4 | 44140 | 1315 | 1.391 | 28.078 | $0.010406 |
| 2 | S2 think and vote (k = 5) | 15/20 | 0 | 222700 | 11109 | 8.078 | 159.222 | $0.057871 |
| 2 | S3 tools | 17/20 | 0 | 49512 | 4198 | 3.875 | 79.694 | $0.014940 |

**Per question (run 1):**

| Question | S1 | S2 | S3 |
|---|:---:|:---:|:---:|
| Q-01 | ✓ | ✓ | ✓ |
| Q-02 | ✓ | ✓ | ✓ |
| Q-03 | ✓ | ✓ | ✓ |
| Q-04 | ✓ | ✓ | ✓ |
| Q-05 | ✗ | ✗ | ✓ |
| Q-06 | ✗ | ✓ | ✗ |
| Q-07 | ✗ | ✓ | ✓ |
| Q-08 | ✓ | ✓ | ✗ |
| Q-09 | ✓ | ✓ | ✓ |
| Q-10 | ✓ | ✓ | ✓ |
| Q-11 | ✗ | ✓ | ✓ |
| Q-12 | ✗ | ✓ | ✓ |
| Q-13 | ✗ | ✓ | ✓ |
| Q-14 | ✓ | ✗ | ✓ |
| Q-15 | ✗ | ✓ | ✓ |
| Q-16 | ✗ | ✗ | ✗ |
| Q-17 | ✗ | ✗ | ✗ |
| Q-18 | ✗ | ✗ | ✗ |
| Q-19 | ✗ | ✓ | ✓ |
| Q-20 | ✗ | ✗ | ✓ |

**Per question (run 2):**

| Question | S1 | S2 | S3 |
|---|:---:|:---:|:---:|
| Q-01 | ✓ | ✓ | ✓ |
| Q-02 | ✓ | ✓ | ✓ |
| Q-03 | ✓ | ✓ | ✓ |
| Q-04 | ✓ | ✓ | ✓ |
| Q-05 | ✗ | ✗ | ✓ |
| Q-06 | ✗ | ✓ | ✗ |
| Q-07 | ✓ | ✓ | ✓ |
| Q-08 | ✓ | ✓ | ✓ |
| Q-09 | ✓ | ✓ | ✓ |
| Q-10 | ✓ | ✓ | ✓ |
| Q-11 | ✗ | ✓ | ✓ |
| Q-12 | ✗ | ✓ | ✓ |
| Q-13 | ✗ | ✓ | ✓ |
| Q-14 | ✗ | ✓ | ✓ |
| Q-15 | ✗ | ✗ | ✓ |
| Q-16 | ✗ | ✗ | ✗ |
| Q-17 | ✗ | ✗ | ✓ |
| Q-18 | ✗ | ✓ | ✗ |
| Q-19 | ✗ | ✓ | ✓ |
| Q-20 | ✗ | ✗ | ✓ |

**Cost calculation:**

I used the published OpenAI list prices for `gpt-5.6-luna`: $0.20 per million input tokens and $1.20 per million output tokens.

`Cost = (input tokens × 0.20 + output tokens × 1.20) / 1,000,000`

These are estimated uncached list-price costs, not verified account charges. Prompt caching may reduce the actual billed amount.

Source: https://developers.openai.com/api/docs/models/gpt-5.6-luna

I counted tokens from every recorded API call, including all five samples in S2 and all tool-calling rounds in S3.

---

## Part C — Explain and choose (Hard)

### C1 — Does the tool description matter?

I tested five questions using the original lookup description and the vague description `Looks things up.` I kept the model, question, tool implementation and other settings unchanged.

| Question | Calls (your description) | Calls (vague) | Answer (yours) | Answer (vague) |
|---|---:|---:|---|---|
| Q-01 | 7 | 7 | Ossbridge / 4.6 | Ossbridge / 4.6 |
| Q-05 | 6 | 7 | Coldharbour / 14235.0 | Coldharbour / 14235.0 |
| Q-08 | 6 | 8 | UNANSWERED / 0.0 | Brightwater / 72.46 |
| Q-09 | 7 | 7 | Millbrook / 0.6 | Millbrook / 0.6 |
| Q-11 | 10 | 10 | Redfen / 56.10 | Redfen / 56.10 |

**Changes in lookup inputs:**

**Q-01:**
The same lookup inputs were used (possibly in a different order).

**Q-05:**
The same lookup inputs were used (possibly in a different order).

**Q-08:**
Original-only inputs: `region: water_use`; `region: water_use`; `region: ml_to_m3`.
Vague-only inputs: `Brightwater: water_use`; `Brightwater: water_tariff`; `Millbrook: water_use`; `Millbrook: water_tariff`.

**Q-09:**
The same lookup inputs were used (possibly in a different order).

**Q-11:**
The same lookup inputs were used (possibly in a different order).

**My interpretation:**

The original description answered 4/5 questions correctly, while the vague description answered 5/5 correctly.

On Q-05, the vague description required one more tool call but the final answer did not change. On Q-08, it required two more calls and returned the correct answer, while the original run was wrong.

This does not prove that vague descriptions are better. The model may take different paths across API runs, even with the same settings. The description can affect how the model chooses tools, but five questions with one observation per version are not enough to separate that effect from run-to-run variation.

My conclusion is that clear tool descriptions are still useful because they explain the correct fields, data sources and limitations. I would keep the detailed description for a more reliable system.

Full logs: `outputs/c1_vague/`.

### C2 — Three mistakes explained

#### Mistake 1: S1 direct, Q-05, Run 1

**What the model did:**

From my real log:

> ANSWER: Stonecairn | 20,359

The model selected Stonecairn, but the correct answer
was Coldharbour with a difference of 14,235 tenge
per resident.

I checked the original documents NR-06 and NR-12:

- Stonecairn: 2,884.6 million tenge / 14,926 residents
  = 193,260.08 tenge per resident.
- Coldharbour: 2,366.9 million tenge / 11,407 residents
  = 207,495.40 tenge per resident.
- Difference = 14,235.31 tenge per resident.

**Why I think it happened:**

S1 had to read the documents, select the numbers,
divide and compare without a calculator tool.
It produced the wrong winner and numerical result.
The saved response does not show its intermediate
calculations, so I cannot prove the exact internal
step that caused the mistake.

A calculator would make the division and subtraction
more reliable and easier to check.

#### Mistake 2: S2 think and vote, Q-14, Run 1

**What the model did:**

From the real voting result:

> ANSWER: Ashgrove | 4.7

All five samples produced Ashgrove with a difference
of 4.7 litres per resident per day.

The correct calculations are:

- Tarnvale: 199.8341 litres per resident per day.
- Ashgrove: 204.6868 litres per resident per day.
- Difference: 4.8528, which rounds to 4.9.

In the samples, the model used approximately 199.9
and 204.6, then subtracted them to get 4.7.
These intermediate approximations were inaccurate.

**Why voting did not help:**

The five answers repeated the same numerical mistake.
Majority voting can reduce some random errors if
different samples make different mistakes.
It cannot correct a systematic error shared by all
five samples. In this case, five calls increased
the token cost without fixing the calculation.

#### Mistake 3: S3 tools, Q-06, Run 1

**What the model did:**

The real tool log contains these results:

- Redfen population: 20,934 (NR-09).
- Kelmarsh population: 24,117 (NR-04).
- Ossford population: 30,982 (NR-02).
- Calculator result: 20,934 + 24,117 - 30,982 = 14,069.

The final model response was:

> ANSWER: Combined population is larger | 14069.0

The expected name was `yes`, but the model wrote
`Combined population is larger`.

**Why it was marked wrong:**

This was not an arithmetic error. The calculator
returned the correct difference of 14,069.
However, my pre-defined scoring rule requires the
name in the final answer to match exactly.
The model did not follow the required yes/no format.

I kept this result marked as wrong because I should
not change my scoring rule after the experiment.

**Why the loop used several rounds:**

This question needed 3 API rounds and
4 tool calls. The model requested
population values, received the tool results,
calculated the difference, and wrote the answer.

The input tokens per round were: 500, 683, 732.

The later calls used more input tokens because
the conversation included earlier model messages,
tool requests and returned results.

**What I learned from the three mistakes:**

S1 can make factual or numerical mistakes when doing
everything directly. S2 can reduce some unstable
answers, but repeated reasoning does not guarantee
correct arithmetic. S3 makes the calculation
verifiable, but the final model response can still
break the required output format.

For a future version, I would validate the final
answer format before accepting it, while keeping
the original experimental results unchanged.

### C3 — Which strategy I would use, and what would change it

**My choice: S3 — Tools**

I would choose S3 for the Nine Rivers questions because
it gave the best accuracy across my two runs.

My results were:

| Strategy | Average accuracy | Average total tokens per run | Average median time | Estimated cost per run |
|---|---:|---:|---:|---:|
| S1 Direct | 40.0% | 45,466 | 1.364 s | $0.01042 |
| S2 Think and Vote | 72.5% | 233,797 | 7.801 s | $0.05786 |
| S3 Tools | 80.0% | 52,300 | 3.875 s | $0.01464 |

These costs are estimates based on the price assumptions
in Part B4, not verified invoice amounts.

**Why I chose S3:**

S3 answered 32 out of 40 question attempts correctly,
compared with 29 out of 40 for S2 and 16 out of 40 for S1.

S3 also used fewer tokens than S2. My estimated cost
for S2 was about 4.0 times the cost of S3.

I think S3 is useful for this task because it separates
retrieving information from mathematical calculations.
I can inspect the source documents and the calculator
results when something goes wrong.

**Why I did not choose S1:**

S1 was the fastest and cheapest strategy, but it only
achieved 40.0% accuracy. It sometimes made
incorrect calculations or chose the wrong district.
For this homework, accurate numerical answers are
more important than saving one or two seconds.

**Why I did not choose S2:**

S2 achieved 72.5% accuracy, which was much
better than S1, but still lower than S3.
It required five independent model responses for each
question, which increased both token usage and time.
The five answers could also repeat the same mistake,
as happened in Q-14.

**Situations that would change my choice:**

1. **Very strict time limit:** I might choose S1 for
   simple questions that do not require calculations.
   It had the shortest median response time. I would
   only do this when the lower accuracy is acceptable.

2. **Very small API budget:** I might choose S1 for
   low-risk questions because it had the lowest
   estimated cost. If accuracy was important, I would
   still prefer S3 when the budget allowed it.

3. **Many more documents:** If there were 1,000 times
   more documents, I would choose a tool-based method,
   but I would improve lookup with an efficient search
   index or retrieval system. The current simple
   document lookup would not scale well.

4. **No external tools allowed:** I would choose S2
   over S1 when accuracy mattered more than cost,
   because S2 performed better in my experiment.

Overall, S3 gave me the best balance of accuracy,
time and estimated cost for this particular task.

### C4 — How sure I can be

**How different were my two runs?**

| Strategy | Run 1 | Run 2 | Difference |
|---|---:|---:|---:|
| S1 | 8/20 | 8/20 | 0 questions |
| S2 | 14/20 | 15/20 | 1 question |
| S3 | 15/20 | 17/20 | 2 questions |

S1 had the same total accuracy in both runs, but
that does not mean it answered the exact same
questions correctly.

The questions that changed from correct to incorrect,
or vice versa, were:

- S1: Q-07, Q-14.
- S2: Q-14, Q-15, Q-18.
- S3: Q-08, Q-17.

**Is the difference between the two best strategies
larger than the variation?**

S3 achieved an average accuracy of 80.0%,
while S2 achieved 72.5%.

The difference was 7.5 percentage points.

In Run 1, S3 answered one more question correctly
than S2. In Run 2, it answered two more correctly.

However, S3 itself changed by two correct answers
between runs. This variation is large compared
with the advantage of S3 over S2.

Therefore, I cannot say that S3 is always better
than S2 based on this experiment alone.

**How many questions would I need?**

I would test at least 200 new and varied questions,
and preferably several hundred, with repeated runs.
I would include different types of questions,
such as simple retrieval, calculations, unit
conversions and corrections.

I would also compare the strategies on exactly the
same questions and report uncertainty, not only
average accuracy.

**Other limitations:**

- I tested only one fictional document collection.
- The 20 questions are a small sample.
- Both runs used the same questions, so they are not
  40 fully independent questions.
- The model can vary between API runs.
- My scoring rule allows a small numerical tolerance.
  This can count slightly incorrect rounding as correct.
- Strict final-answer formatting can mark a
  mathematically correct response as wrong, like Q-06.
- My cost calculations are estimates rather than
  verified billing amounts.

**My conclusion:**

S3 was the best strategy in my experiment,
but the evidence is not strong enough to prove
that it will always be the best choice.
I would need more questions and repeated tests
before trusting a small accuracy difference.

### Final questions

1. **When the model sends a `tool_calls` message, what has actually run so far?**

The model has only requested a function call, but the function has not executed yet. My Python loop reads the request, checks its arguments, runs the correct tool, and sends the result back to the model. The model then continues generating its answer.

2. **Why does `arguments` arrive as a string, and what goes wrong if you pass it straight into your function?**

Arguments arrive as a JSON string because the model generates a structured request that must be decoded by my program. I use `json.loads()` to convert the string into a Python dictionary and validate its fields. Without parsing and validation, the function may receive the wrong data type or unexpected arguments.

3. **How many tokens do your two tool definitions add to every S3 request?**

I measured the overhead with two short API requests using the same messages. The request without tools used 18 input tokens, while the request with both tool definitions used 386, so the difference was 368 tokens. This measures the definitions' overhead in my controlled test; actual request sizes also depend on conversation history.

4. **How much more did S2 cost than S1?**

In my two experiments, the average estimated cost of S1 was $0.010420 per run, compared with $0.057856 for S2. S2 was approximately 5.55 times more expensive because it generated five independent responses for every question instead of one. These figures are based on my token usage and estimated API prices, not verified billing charges.

5. **Which question needed the most rounds in S3, and why?**

Q-08 in Run 2 took the most rounds, with 6 API rounds, 7 lookup calls and 1 calculator call. The question compares the water payments of Brightwater and Millbrook, requiring water-use figures, the regional tariff and consistent units. The multiple lookups and returned results increased the number of exchanges before the final answer.

6. **What would you change in `lookup` if there were 100,000 documents?**

I would not scan all documents with simple regular expressions for every question. I would create a search index, such as BM25 or an embedding-based retrieval system, and return only the most relevant results. I would also store document dates and correction information so archived data does not replace current facts.

7. **What stops `calculate` from running dangerous code? Could the model still make it misbehave?**

My calculator uses Python's `ast` module and allows only numeric constants and selected arithmetic operators, without `eval()` or `exec()`. It rejects function calls, attribute access, unsupported operators, division by zero and oversized calculations. The model can still send invalid or misleading mathematical expressions, so input validation does not guarantee that every numerical answer is correct.

8. **For which kind of question did tools help most, and for which did they not help at all?**

Tools helped most with multi-step numerical questions where the model needed to retrieve several facts and perform calculations, such as Q-05, where S3 was correct in both runs while S1 and S2 were wrong. They did not improve Q-16 in my experiment because all three strategies were scored wrong in both runs. I also learned from Q-06 that tools can calculate correctly while the final model response still fails the required answer format.
