import json
import statistics
from pathlib import Path

import b4_strategies as b4
import strategies

ROOT = Path(__file__).resolve().parent
OUTPUTS = ROOT / "outputs" / "b4"

assert b4.MODEL == strategies.MODEL


def load_questions():
    return json.loads(
        (ROOT / "data/questions.json").read_text(
            encoding="utf-8"
        )
    )


def run_one(client, run_number, strategy, question):
    qid = question["id"]

    folder = OUTPUTS / f"run_{run_number}"
    folder.mkdir(parents=True, exist_ok=True)

    path = folder / f"{strategy}_{qid}.json"

    # Resume without paying again for finished requests
    if path.exists():
        previous = json.loads(
            path.read_text(encoding="utf-8")
        )
        if previous.get("status") in (
            "answered", "unanswered"
        ):
            return previous

    try:
        if strategy == "S1":
            result = b4.run_s1(client, question)

        elif strategy == "S2":
            result = b4.run_s2(client, question)

        elif strategy == "S3":
            result = strategies.run_b3(
                client=client,
                question_id=qid,
                question=question["question"],
                decimals=question["decimals"],
                output_path=str(path)
            )

            result["score"] = b4.score_answer(
                result.get("answer"), question
            )
        else:
            raise ValueError("Unknown strategy")

        if result.get("status") == "api_error":
            raise RuntimeError(
                "S3 API error: " +
                str(result.get("error"))
            )

        result["status"] = (
            "unanswered"
            if result["score"]["unanswered"]
            else "answered"
        )

        result["strategy"] = strategy
        result["question_id"] = qid
        result["run_number"] = run_number
        result["model"] = b4.MODEL

        path.write_text(
            json.dumps(
                result, indent=2, ensure_ascii=False
            ),
            encoding="utf-8"
        )

        return result

    except Exception as exc:
        error = {
            "run_number": run_number,
            "strategy": strategy,
            "question_id": qid,
            "status": "api_error",
            "error_type": type(exc).__name__
        }

        path.write_text(
            json.dumps(error, indent=2),
            encoding="utf-8"
        )

        raise RuntimeError(
            f"{strategy} failed on {qid}: "
            f"{type(exc).__name__}"
        ) from exc


def run_batch(client, run_number, question_ids=None):
    questions = load_questions()

    if question_ids is not None:
        questions = [
            q for q in questions
            if q["id"] in question_ids
        ]

    results = []

    for i, q in enumerate(questions, 1):
        print(
            f"\nRUN {run_number} | "
            f"Question {i}/{len(questions)} | "
            f"{q['id']}",
            flush=True
        )

        for strategy in ("S1", "S2", "S3"):
            result = run_one(
                client, run_number, strategy, q
            )
            results.append(result)

            score = result["score"]

            print(
                f"  {strategy}: "
                f"{'CORRECT' if score['correct'] else 'WRONG'} "
                f"| status={result['status']} "
                f"| input={result['input_tokens']} "
                f"| output={result['output_tokens']}",
                flush=True
            )

    print(
        f"\n✅ Batch finished: {len(results)} results"
    )
    return results


def summarize_run(run_number):
    folder = OUTPUTS / f"run_{run_number}"
    summary = []

    for strategy in ("S1", "S2", "S3"):
        paths = sorted(
            folder.glob(f"{strategy}_Q-*.json")
        )

        records = [
            json.loads(p.read_text(encoding="utf-8"))
            for p in paths
        ]

        if len(records) != 20:
            print(
                f"Run {run_number} {strategy}: "
                f"{len(records)}/20 questions"
            )
            continue

        if any(
            r.get("status") == "api_error"
            for r in records
        ):
            print(
                f"Run {run_number} {strategy}: API errors"
            )
            continue

        times = [
            r.get("seconds", r.get("total_seconds", 0))
            for r in records
        ]

        summary.append({
            "run": run_number,
            "strategy": strategy,
            "correct": sum(
                r["score"]["correct"] for r in records
            ),
            "unanswered": sum(
                r["score"]["unanswered"] for r in records
            ),
            "input_tokens": sum(
                r["input_tokens"] for r in records
            ),
            "output_tokens": sum(
                r["output_tokens"] for r in records
            ),
            "median_seconds": round(
                statistics.median(times), 3
            ),
            "total_seconds": round(sum(times), 3)
        })

    return summary
