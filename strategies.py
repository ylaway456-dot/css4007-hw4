import json
import re
import time
from pathlib import Path
from tools import lookup, calculate

ROOT = Path(__file__).resolve().parent
MODEL = "gpt-5.6-luna"
MAX_ROUNDS = 8


def get_tool_definitions():
    """Read the exact definitions from Part A2."""
    md = (ROOT / "SUBMISSION.md").read_text(
        encoding="utf-8"
    )

    result = []

    for name in ("lookup", "calculate"):
        pattern = (
            r"####\s+`" + name +
            r"`\s*```json\s*(.*?)\s*```"
        )

        match = re.search(pattern, md, flags=re.S)

        if match is None:
            raise ValueError(
                f"Tool definition not found: {name}"
            )

        data = json.loads(match.group(1))
        assert data["function"]["name"] == name
        result.append(data)

    return result


def call_local_tool(name, arguments_string):
    """Validate JSON before executing a tool."""
    try:
        args = json.loads(arguments_string)
    except (ValueError, TypeError):
        return {
            "ok": False,
            "error": "Invalid JSON arguments"
        }

    expected = {
        "lookup": {"district", "field"},
        "calculate": {"expression"}
    }

    if name not in expected:
        return {"ok": False, "error": "Unknown tool"}

    if not isinstance(args, dict) or set(args) != expected[name]:
        return {
            "ok": False,
            "error": "Wrong argument names"
        }

    if not all(isinstance(x, str) for x in args.values()):
        return {
            "ok": False,
            "error": "Arguments must be strings"
        }

    try:
        if name == "lookup":
            return lookup(args["district"], args["field"])

        return calculate(args["expression"])

    except Exception as exc:
        return {
            "ok": False,
            "error": type(exc).__name__
        }


def run_b3(client, question_id, question, decimals, output_path=None):
    """Run the real tool-calling conversation."""

    messages = [
        {
            "role": "system",
            "content": (
                "Answer questions about the fictional "
                "Nine Rivers Region. You do not have the "
                "documents. Get facts using lookup and "
                "perform arithmetic with calculate. "
                "Do not invent figures. Use 2025 figures, "
                "current profiles and corrections when "
                "relevant. Do not round intermediate "
                "results. Finish with a line exactly "
                "like: ANSWER: Name | 0.0. "
                "If reliable facts are missing, "
                "say UNANSWERED."
            )
        },
        {
            "role": "user",
            "content": (
                question +
                f"\nRound the final number to {decimals} "
                "decimal places."
            )
        }
    ]

    log = {
        "question_id": question_id,
        "model": MODEL,
        "max_rounds": MAX_ROUNDS,
        "status": "unanswered",
        "answer": None,
        "api_rounds": [],
        "tool_calls": [],
        "input_tokens": 0,
        "output_tokens": 0,
        "error": None
    }

    started = time.perf_counter()

    try:
        for n in range(1, MAX_ROUNDS + 1):

            request_start = time.perf_counter()

            response = client.chat.completions.create(
                model=MODEL,
                reasoning_effort="none",
                messages=messages,
                tools=get_tool_definitions(),
                tool_choice=(
                    "required" if n == 1 else "auto"
                ),
                timeout=90
            )

            usage = response.usage

            in_tokens = (
                usage.prompt_tokens if usage else 0
            )
            out_tokens = (
                usage.completion_tokens if usage else 0
            )

            log["input_tokens"] += in_tokens
            log["output_tokens"] += out_tokens

            log["api_rounds"].append({
                "round": n,
                "seconds": round(
                    time.perf_counter() - request_start, 3
                ),
                "input_tokens": in_tokens,
                "output_tokens": out_tokens
            })

            assistant = response.choices[0].message

            # Preserve the model's tool_calls and IDs.
            messages.append(
                assistant.model_dump(exclude_none=True)
            )

            if not assistant.tool_calls:
                log["answer"] = assistant.content or ""

                valid = re.search(
                    r"(?m)^ANSWER:\s*[^|\n]+\|\s*"
                    r"[-+]?\d+(?:\.\d+)?\s*$",
                    log["answer"]
                )

                log["status"] = (
                    "answered"
                    if valid and log["tool_calls"]
                    else "unanswered"
                )
                break

            for call in assistant.tool_calls:
                t0 = time.perf_counter()

                outcome = call_local_tool(
                    call.function.name,
                    call.function.arguments
                )

                log["tool_calls"].append({
                    "round": n,
                    "tool_call_id": call.id,
                    "tool": call.function.name,
                    "arguments": call.function.arguments,
                    "result": outcome,
                    "seconds": round(
                        time.perf_counter() - t0, 6
                    )
                })

                # Every tool_call_id gets its own result.
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(
                        outcome, ensure_ascii=False
                    )
                })

        else:
            log["stop_reason"] = "8-round limit reached"

    except Exception as exc:
        log["status"] = "api_error"
        log["error"] = {
            "type": type(exc).__name__,
            "http_status": getattr(
                exc, "status_code", None
            ),
            "code": getattr(exc, "code", None)
        }

    finally:
        log["total_seconds"] = round(
            time.perf_counter() - started, 3
        )
        log["conversation"] = messages

        output = ROOT / "outputs"
        output.mkdir(exist_ok=True)

        (Path(output_path) if output_path else (output / f"b3_{question_id}.json")).write_text(
            json.dumps(
                log, indent=2, ensure_ascii=False
            ),
            encoding="utf-8"
        )

    return log
