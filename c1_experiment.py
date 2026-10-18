import copy
import json
from pathlib import Path

import strategies
from b4_strategies import parse_answer, score_answer

ROOT = Path(__file__).resolve().parent
IDS = ["Q-01", "Q-05", "Q-08", "Q-09", "Q-11"]


def run_c1(client=None, force=False):
    questions = json.loads(
        (ROOT / "data/questions.json").read_text(
            encoding="utf-8"
        )
    )
    question_map = {q["id"]: q for q in questions}

    folder = ROOT / "outputs/c1_vague"
    folder.mkdir(parents=True, exist_ok=True)

    original_loader = strategies.get_tool_definitions
    vague_tools = copy.deepcopy(original_loader())

    for tool in vague_tools:
        if tool["function"]["name"] == "lookup":
            tool["function"]["description"] = "Looks things up."

    def vague_loader():
        return copy.deepcopy(vague_tools)

    rows = []

    def answer_text(log):
        parsed = parse_answer(log.get("answer"))
        if parsed is None:
            return "UNANSWERED"
        return f"{parsed['name']} / {parsed['number']}"

    try:
        strategies.get_tool_definitions = vague_loader

        for qid in IDS:
            q = question_map[qid]
            path = folder / f"{qid}.json"

            if force or not path.exists():
                if client is None:
                    raise RuntimeError("API client required for new run")

                vague = strategies.run_b3(
                    client, qid, q["question"], q["decimals"],
                    output_path=str(path)
                )
            else:
                vague = json.loads(
                    path.read_text(encoding="utf-8")
                )

            if vague["status"] != "answered":
                raise RuntimeError(f"Incomplete result: {qid}")

            baseline = json.loads(
                (ROOT / "outputs/b4/run_1" /
                 f"S3_{qid}.json").read_text(
                    encoding="utf-8"
                )
            )

            def inputs(log):
                return [
                    c["arguments"]
                    for c in log["tool_calls"]
                    if c["tool"] == "lookup"
                ]

            rows.append({
                "question": qid,
                "original_calls": len(baseline["tool_calls"]),
                "vague_calls": len(vague["tool_calls"]),
                "original_inputs": inputs(baseline),
                "vague_inputs": inputs(vague),
                "original_answer": answer_text(baseline),
                "vague_answer": answer_text(vague),
                "original_correct": baseline["score"]["correct"],
                "vague_correct": score_answer(
                    vague["answer"], q
                )["correct"]
            })
    finally:
        strategies.get_tool_definitions = original_loader

    (folder / "comparison.json").write_text(
        json.dumps(rows, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    return rows
