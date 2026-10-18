import json
import re
import time
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path

from openai import BadRequestError

ROOT = Path(__file__).resolve().parent
MODEL = "gpt-5.6-luna"
K = 5


def get_corpus():
    path = ROOT / "data/corpus.jsonl"
    docs = [
        json.loads(line)
        for line in path.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]

    assert len(docs) == 17

    return "\n\n".join(
        f"[{d['id']}] {d['title']}\n{d['text']}"
        for d in docs
    )


def build_messages(question, decimals, strategy):
    instructions = (
        "Answer questions using the provided fictional "
        "Nine Rivers Region documents. Use current records "
        "and correction notices instead of archived data. "
        "Pay attention to units and do not invent numbers. "
        "Keep full precision until the final result. "
        f"Round the final value to {decimals} decimal places. "
        "Finish with exactly one line in this format: "
        "ANSWER: name | number. "
        "Use yes or no when appropriate. "
        "If reliable facts are missing, write UNANSWERED."
    )

    if strategy == "S2":
        instructions += (
            " Think through the facts and calculations "
            "step by step. Show a concise calculation "
            "summary before the final answer."
        )

    return [
        {
            "role": "system",
            "content": (
                instructions
                + "\n\nDOCUMENTS:\n"
                + get_corpus()
            )
        },
        {"role": "user", "content": question}
    ]


def parse_answer(text):
    """
    Parse an ANSWER line, allowing trailing units.
    Examples:
    ANSWER: Millbrook | 0.6
    ANSWER: Millbrook | 0.6 residents per km2
    """
    if not text:
        return None

    pattern = (
        r"(?im)^[ \t]*ANSWER:[ \t]*"
        r"([^|\n]+?)[ \t]*\|[ \t]*"
        r"([+-]?(?:\d{1,3}(?:,\d{3})+|\d+)"
        r"(?:\.\d+)?)"
        r"(?=[ \t]|%|$)[^\n]*$"
    )

    matches = re.findall(pattern, text)

    if not matches:
        return None

    name, number = matches[-1]

    try:
        value = Decimal(number.replace(",", ""))
    except InvalidOperation:
        return None

    return {
        "name": name.strip(),
        "number": str(value)
    }


def score_answer(text, question):
    parsed = parse_answer(text)

    if parsed is None:
        return {
            "correct": False,
            "unanswered": True
        }

    name_ok = (
        parsed["name"].casefold()
        == question["answer"].strip().casefold()
    )

    places = int(question["decimals"])
    tolerance = Decimal(1).scaleb(-places)

    actual = Decimal(parsed["number"])
    expected = Decimal(str(question["value"]))

    number_ok = abs(actual - expected) <= tolerance

    return {
        "correct": bool(name_ok and number_ok),
        "unanswered": False,
        "name_correct": name_ok,
        "number_correct": number_ok,
        "parsed": parsed
    }


def request_sample(client, messages, temperature=None):
    kwargs = {
        "model": MODEL,
        "messages": messages,
        "reasoning_effort": "none",
        "timeout": 90
    }

    if temperature is not None:
        kwargs["temperature"] = temperature

    started = time.perf_counter()

    try:
        response = client.chat.completions.create(**kwargs)

    except BadRequestError as e:
        message = str(e).lower()

        if (
            "temperature" in message
            and (
                "unsupported" in message
                or "not supported" in message
                or "does not support" in message
                or "only the default" in message
            )
            and temperature is not None
        ):
            # Model cannot use custom temperature.
            kwargs.pop("temperature")
            response = client.chat.completions.create(
                **kwargs
            )
        else:
            raise

    elapsed = time.perf_counter() - started
    usage = response.usage

    return {
        "answer": (
            response.choices[0].message.content or ""
        ),
        "seconds": round(elapsed, 4),
        "input_tokens": (
            usage.prompt_tokens if usage else 0
        ),
        "output_tokens": (
            usage.completion_tokens if usage else 0
        ),
        "temperature_used": kwargs.get("temperature"),
        "finish_reason": response.choices[0].finish_reason
    }


def run_s1(client, question):
    messages = build_messages(
        question["question"],
        question["decimals"],
        "S1"
    )

    sample = request_sample(client, messages)

    return {
        "strategy": "S1",
        "question_id": question["id"],
        "answer": sample["answer"],
        "samples": [sample],
        "input_tokens": sample["input_tokens"],
        "output_tokens": sample["output_tokens"],
        "seconds": sample["seconds"],
        "score": score_answer(
            sample["answer"], question
        )
    }


def run_s2(client, question):
    messages = build_messages(
        question["question"],
        question["decimals"],
        "S2"
    )

    samples = []
    votes = []
    started = time.perf_counter()

    for i in range(K):
        sample = request_sample(
            client, messages, temperature=0.7
        )
        samples.append(sample)

        parsed = parse_answer(sample["answer"])

        if parsed:
            key = (
                parsed["name"].casefold(),
                str(Decimal(parsed["number"]).normalize())
            )
            votes.append((key, parsed))

    if votes:
        counts = Counter(key for key, _ in votes)
        winning_key = counts.most_common(1)[0][0]
        winning = next(
            parsed for key, parsed in votes
            if key == winning_key
        )
        answer = (
            f"ANSWER: {winning['name']} | "
            f"{winning['number']}"
        )
    else:
        answer = "UNANSWERED"

    return {
        "strategy": "S2",
        "question_id": question["id"],
        "answer": answer,
        "samples": samples,
        "input_tokens": sum(
            s["input_tokens"] for s in samples
        ),
        "output_tokens": sum(
            s["output_tokens"] for s in samples
        ),
        "seconds": round(
            time.perf_counter() - started, 4
        ),
        "temperature_supported": all(
            s["temperature_used"] is not None
            for s in samples
        ),
        "score": score_answer(answer, question)
    }
