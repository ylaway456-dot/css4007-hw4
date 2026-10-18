import json
import re
import difflib
from pathlib import Path

BASE = Path(__file__).resolve().parent
CORPUS = BASE / "data" / "corpus.jsonl"

PATTERNS = {
    "population_2020": [
        r"2020 census had recorded ([\d,]+)",
        r"Census population:\s*([\d,]+) in 2020",
        r"(?:up|down) from ([\d,]+) at the 2020 census"
    ],
    "population_2025": [
        r"2025 census recorded ([\d,]+) residents",
        r"Census population:\s*[\d,]+ in 2020 and ([\d,]+) in 2025",
        r"2025 census counted ([\d,]+) residents"
    ],
    "area_km2": [
        r"covers ([\d,.]+) square kilometres",
        r"over ([\d,.]+) square kilometres",
        r"on an area of ([\d,.]+) square kilometres"
    ],
    "founded_year": [r"founded in (\d{4})"],
    "schools": [
        r"There are ([\d,]+) schools",
        r"has ([\d,]+) schools",
        r"runs ([\d,]+) schools"
    ],
    "pupils": [
        r"attended by ([\d,]+) pupils",
        r"enrolled ([\d,]+) pupils",
        r"schools with ([\d,]+) pupils"
    ],
    "budget_million_tenge": [
        r"budget for 2025 was set at ([\d,.]+) million tenge",
        r"2025 budget amounted to ([\d,.]+) million tenge",
        r"2025 budget was ([\d,.]+) million tenge"
    ],
    "water_use": [
        r"(?:came to|Households used)\s*([\d,.]+)\s*(megalitres|cubic metres)"
    ],
    "road_km": [
        r"paved road network is ([\d,.]+) km long",
        r"keeps ([\d,.]+) km of paved road",
        r"maintains ([\d,.]+) km of paved road"
    ]
}

UNITS = {
    "population_2020": "residents",
    "population_2025": "residents",
    "area_km2": "km2",
    "founded_year": "year",
    "schools": "schools",
    "pupils": "pupils",
    "budget_million_tenge": "million tenge",
    "road_km": "km"
}

def _number(text):
    number = float(text.replace(",", ""))
    return int(number) if number.is_integer() else number

def _load_corpus():
    with CORPUS.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]

def lookup(district, field):
    try:
        if not isinstance(district, str) or not isinstance(field, str):
            return {"ok": False, "error": "Inputs must be strings"}

        district = district.strip()
        field = field.strip()

        if not district or not field or len(district) > 80 or len(field) > 80:
            return {"ok": False, "error": "Invalid input length"}

        if field not in list(PATTERNS) + ["water_tariff", "ml_to_m3"]:
            return {"ok": False, "error": "Invalid field"}

        docs = _load_corpus()

        if field in ("water_tariff", "ml_to_m3"):
            if district.lower() != "region":
                return {"ok": False, "error": "Use district='region'"}

            document = next(d for d in docs if d["id"] == "NR-15")

            if field == "water_tariff":
                pattern = r"regional household water tariff is ([\d,.]+) tenge per cubic metre"
                unit = "tenge/m3"
            else:
                pattern = r"One megalitre is ([\d,]+) cubic metres"
                unit = "m3/ML"

            match = re.search(pattern, document["text"], re.I)

            if not match:
                return {"ok": False, "error": "Regional fact missing"}

            return {
                "ok": True,
                "value": _number(match.group(1)),
                "unit": unit,
                "source_id": "NR-15"
            }

        current = {}
        for doc in docs:
            match = re.fullmatch(
                r"(.+?) district profile \(2025\)",
                doc["title"]
            )
            if match:
                current[match.group(1).lower()] = doc

        if (
            "archived" in district.lower()
            or "2019" in district
            or district.upper() in ("NR-13", "NR-14")
        ):
            return {
                "ok": False,
                "error": "Archived profiles are superseded by 2025 profiles"
            }

        doc = current.get(district.lower())

        if doc is None:
            names = [
                d["title"].split(" district profile")[0]
                for d in current.values()
            ]
            suggestions = difflib.get_close_matches(
                district, names, n=3, cutoff=0.5
            )
            return {
                "ok": False,
                "error": "District not found",
                "suggestions": suggestions
            }

        source = doc["id"]
        text = doc["text"]
        patterns = PATTERNS[field]

        if field == "area_km2" and district.lower() == "brightwater":
            correction = next(
                d for d in docs if d["id"] == "NR-16"
            )
            text = correction["text"]
            source = "NR-16"
            patterns = [
                r"correct area is ([\d,.]+) square kilometres"
            ]

        for pattern in patterns:
            match = re.search(pattern, text, re.I)

            if match:
                unit = (
                    match.group(2)
                    if field == "water_use"
                    else UNITS.get(field)
                )
                return {
                    "ok": True,
                    "value": _number(match.group(1)),
                    "unit": unit,
                    "source_id": source
                }

        return {
            "ok": False,
            "error": f"Missing fact: {field} in {source}"
        }

    except Exception as error:
        return {
            "ok": False,
            "error": f"Lookup failed: {type(error).__name__}"
        }


import ast
import operator
import math

SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv
}

SAFE_UNARY = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg
}

MAX_EXPRESSION_LENGTH = 200
MAX_NUMBER = 10**15
MAX_DEPTH = 25

def calculate(expression):
    """
    Safely evaluate arithmetic without eval or exec.
    Allows numbers, +, -, *, / and parentheses.
    """
    if not isinstance(expression, str):
        return {"ok": False, "error": "Expression must be a string"}

    expression = expression.strip()

    if not expression or len(expression) > MAX_EXPRESSION_LENGTH:
        return {"ok": False, "error": "Invalid expression length"}

    try:
        tree = ast.parse(expression, mode="eval")

        def evaluate(node, depth=0):
            if depth > MAX_DEPTH:
                raise ValueError("Expression too deep")

            if isinstance(node, ast.Constant):
                if type(node.value) not in (int, float):
                    raise ValueError("Only numbers are allowed")
                result = node.value

            elif isinstance(node, ast.UnaryOp) and type(node.op) in SAFE_UNARY:
                value = evaluate(node.operand, depth + 1)
                result = SAFE_UNARY[type(node.op)](value)

            elif isinstance(node, ast.BinOp) and type(node.op) in SAFE_OPERATORS:
                left = evaluate(node.left, depth + 1)
                right = evaluate(node.right, depth + 1)
                result = SAFE_OPERATORS[type(node.op)](left, right)

            else:
                raise ValueError("Unsupported or dangerous expression")

            if not math.isfinite(result) or abs(result) > MAX_NUMBER:
                raise ValueError("Number too large")

            return result

        value = evaluate(tree.body)

        return {
            "ok": True,
            "value": float(value)
        }

    except ZeroDivisionError:
        return {"ok": False, "error": "Division by zero"}

    except (SyntaxError, ValueError, TypeError,
            OverflowError, RecursionError):
        return {"ok": False, "error": "Invalid or unsafe expression"}

    except Exception:
        return {"ok": False, "error": "Calculation failed"}
