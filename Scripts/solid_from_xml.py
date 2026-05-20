from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import random
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from openai import OpenAI


EVAL_PROMPT_V1 = r"""
You are a senior software architecture researcher scoring METHOD-LEVEL structural signals related to SRP, OCP, and DIP in Java.

IMPORTANT:
- Output VALID JSON only.
- No markdown.
- No commentary outside JSON.
- Be conservative. If the method alone is insufficient, set score=1 and add flag "needs_more_context".
- You are NOT inferring intent or domain meaning. You are scoring observable structural signals only.

You are evaluating a SINGLE Java method extracted from a larger system.
Identifiers may have been consistently renamed (e.g., x1, x2). Do NOT infer semantics from names.

---------------------------------------
SCORING RUBRIC (Method-Level Signals)
---------------------------------------

Score per principle:
0 = Violated (clear structural evidence)
1 = Partial / Uncertain (mixed signals OR insufficient context)
2 = Compliant (clear structural evidence)

You MUST include 1-3 evidence items per principle.
Each evidence item MUST cite a concrete construct and include a short quoted snippet from the method (or a very precise description if quoting is impossible).

Principles:

1) SRP — Single Responsibility (method cohesion)
Score whether the method does one cohesive responsibility.

Score=0 if:
- Multiple distinct responsibilities are present (e.g., validates + persists + logs), OR
- Unrelated side effects are mixed (e.g., updates state + UI + IO).

Score=2 if:
- One focused responsibility, OR
- It delegates via at most 3 calls and contains no independent logic beyond delegation sequencing (thin orchestrator).

Score=1 + flag "needs_more_context" if:
- SRP judgement depends on class-level role or broader workflow not visible here.

---

2) OCP — Extension vs. modification RISK SIGNALS (method-level proxy)
You are NOT declaring true OCP compliance for the system. You are scoring whether this method structurally encodes variation such that future requirements likely require modifying THIS method.

Score=0 if:
- if/else or switch chain with 3+ branches encoding behavioral variants, OR
- Hard-coded policy thresholds / magic constants that appear to represent changeable policy, OR
- Repeated copy-modify style branches.

Score=2 if:
- Behavior is delegated to collaborators / polymorphic calls, and branching is minimal (0-2 branches) and not encoding variants.

Score=1 + flag "needs_more_context" if:
- You cannot see whether delegation is polymorphic/strategy-based, OR
- Branching exists but could be simple control flow without representing an extensibility point.

---

3) DIP — Dependency Inversion (replaceable dependency signals)
Score whether the method introduces tight coupling to replaceable concrete collaborators.

Score=0 if:
- Instantiates a likely replaceable collaborator/service (e.g., repository, network client, UI subsystem, persistence service) directly inside the method, OR
- Uses static singletons/globals for replaceable collaborators, OR
- Strong framework coupling that acts as a direct dependency (not just DTOs/events).

IMPORTANT: The following are NOT DIP violations:
- Instantiating collections (ArrayList/HashMap/etc.), strings, primitives, simple data/value objects, iterators/enumerators
- Creating Exceptions
- Creating small helper objects local to the method, when not a replaceable external collaborator

Score=2 if:
- Dependencies are injected via parameters/fields (as abstractions), OR
- No replaceable dependencies appear in the method.

Score=1 + flag "needs_more_context" if:
- A 'new X(...)' appears, but you cannot determine if X is a replaceable collaborator vs a value/helper type.

---------------------------------------
OUTPUT FORMAT (STRICT JSON)
---------------------------------------
{
  "srp": {"score":0|1|2,"label":"Violated|Partial|Compliant","confidence":0.0-1.0,"evidence":["..."],"notes":""},
  "ocp": {"score":0|1|2,"label":"Violated|Partial|Compliant","confidence":0.0-1.0,"evidence":["..."],"notes":""},
  "dip": {"score":0|1|2,"label":"Violated|Partial|Compliant","confidence":0.0-1.0,"evidence":["..."],"notes":""},
  "overall": {"solid_score":0-6,"flags":[]}
}

Rules:
- Evidence must reference specific structural constructs and preferably quote a snippet.
- If insufficient context for SRP or OCP, include flag "needs_more_context".
- Do NOT invent missing hierarchy or intent.
- Confidence must reflect certainty.

METADATA:
id: {{id}}
file: {{file_path}}
startline: {{startline}}
endline: {{endline}}

METHOD CODE:
{{code}}

Evaluate now.
""".strip()


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass
class RunConfig:
    input_path: str = ""
    output_path: str = ""
    model: str = "gpt-5.2"
    resume: bool = False
    temperature: float = 0.0
    top_p: float = 1.0
    max_output_tokens: int = 700
    max_code_chars: int = 14000
    trunc_head_chars: int = 9000
    trunc_tail_chars: int = 3000
    api_retries: int = 4
    json_retries: int = 2
    base_backoff_s: float = 1.0
    max_backoff_s: float = 20.0
    prompt_version: str = "EVAL_PROMPT_V1"

# ---------------------------------------------------------------------------
# Source-block dataclass
# ---------------------------------------------------------------------------

@dataclass
class SourceBlock:
    file_path: str
    startline: int
    endline: int
    code: str
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = f"{self.file_path}:{self.startline}-{self.endline}"

# ---------------------------------------------------------------------------
# XML / regex parsing
# ---------------------------------------------------------------------------

_SOURCE_RE = re.compile(
    r'<source\s+file="(?P<file>[^"]+)"\s+'
    r'startline="(?P<start>\d+)"\s+'
    r'endline="(?P<end>\d+)">\s*'
    r'(?P<code>.*?)\s*'
    r'</source>',
    re.DOTALL,
)


def parse_source_blocks(text: str) -> List[SourceBlock]:
    """Return all <source> blocks found in *text*."""
    blocks: List[SourceBlock] = []
    for m in _SOURCE_RE.finditer(text):
        blocks.append(
            SourceBlock(
                file_path=m.group("file"),
                startline=int(m.group("start")),
                endline=int(m.group("end")),
                code=m.group("code"),
            )
        )
    return blocks

# ---------------------------------------------------------------------------
# Output path derivation
# ---------------------------------------------------------------------------

def derive_output_path(input_path: str) -> str:
    """Derive output JSONL filename from input: 'path/JHotDraw_functions.xml' → 'JHotDraw_SOLID_Eval.jsonl'."""
    base = os.path.basename(input_path)                # JHotDraw_functions.xml
    name = os.path.splitext(base)[0]                   # JHotDraw_functions
    # Remove common TXL suffixes
    for suffix in ("_functions", "_Functions", "_methods", "_Methods", "_source", "_sources"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    return os.path.join(os.path.dirname(input_path) or ".", f"{name}_SOLID_Eval.jsonl")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def append_jsonl(path: str, obj: Dict[str, Any]) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def load_processed_ids(output_path: str) -> Set[str]:
    processed: Set[str] = set()
    if not os.path.exists(output_path):
        return processed
    with open(output_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                rid = rec.get("id")
                if isinstance(rid, str):
                    processed.add(rid)
            except json.JSONDecodeError:
                pass
    return processed


def truncate_code(code: str, cfg: RunConfig) -> Tuple[str, bool]:
    if len(code) <= cfg.max_code_chars:
        return code, False
    head = code[: cfg.trunc_head_chars]
    tail = code[-cfg.trunc_tail_chars:] if cfg.trunc_tail_chars > 0 else ""
    return (
        head
        + "\n/* ... TRUNCATED FOR TOKEN SAFETY ... */\n"
        + tail
    ), True


def fill_prompt(template: str, vars_: Dict[str, Any]) -> str:
    def safe(v: Any) -> str:
        if v is None:
            return ""
        if isinstance(v, (list, tuple)):
            return json.dumps(v, ensure_ascii=False)
        return str(v)

    for key, val in vars_.items():
        template = template.replace("{{" + key + "}}", safe(val))
    # clear any remaining placeholders
    template = re.sub(r"\{\{[a-zA-Z0-9_]+\}\}", "", template)
    return template


def extract_json_object(text: str) -> Dict[str, Any]:
    text = text.strip()
    if text.startswith("{") and text.endswith("}"):
        return json.loads(text)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in model output.")
    return json.loads(text[start: end + 1])


def validate_output_schema(out: Dict[str, Any]) -> None:
    for p in ("srp", "ocp", "dip"):
        if p not in out or not isinstance(out[p], dict):
            raise ValueError(f"Output missing '{p}' dict.")
        for k in ("score", "label", "confidence", "evidence", "notes"):
            if k not in out[p]:
                raise ValueError(f"Output missing '{p}.{k}'.")
        score = out[p]["score"]
        if score not in (0, 1, 2):
            raise ValueError(f"Invalid {p}.score: {score}")
        if out[p]["label"] not in ("Violated", "Partial", "Compliant"):
            raise ValueError(f"Invalid {p}.label: {out[p]['label']}")
        conf = out[p]["confidence"]
        if not (isinstance(conf, (int, float)) and 0.0 <= float(conf) <= 1.0):
            raise ValueError(f"Invalid {p}.confidence: {conf}")
        if not isinstance(out[p]["evidence"], list):
            raise ValueError(f"Invalid {p}.evidence (must be list).")
        if len(out[p]["evidence"]) > 3:
            raise ValueError(f"{p}.evidence exceeds max 3 items.")
        if not isinstance(out[p]["notes"], str):
            raise ValueError(f"Invalid {p}.notes (must be string).")

    if "overall" not in out or not isinstance(out["overall"], dict):
        raise ValueError("Output missing 'overall' dict.")
    if "solid_score" not in out["overall"]:
        raise ValueError("Output missing overall.solid_score")
    if out["overall"]["solid_score"] not in range(0, 7):
        raise ValueError(f"Invalid overall.solid_score: {out['overall']['solid_score']}")
    if "flags" not in out["overall"] or not isinstance(out["overall"]["flags"], list):
        raise ValueError("Output missing overall.flags list.")


def backoff_sleep(attempt: int, cfg: RunConfig) -> None:
    base = cfg.base_backoff_s * (2 ** max(0, attempt - 1))
    sleep_s = min(cfg.max_backoff_s, base) * (0.7 + random.random() * 0.6)
    time.sleep(sleep_s)

# ---------------------------------------------------------------------------
# OpenAI interaction
# ---------------------------------------------------------------------------

def call_model(client: OpenAI, prompt: str, cfg: RunConfig) -> str:
    """Call OpenAI Responses API and return raw text."""
    resp = client.responses.create(
        model=cfg.model,
        input=prompt,
        temperature=cfg.temperature,
        top_p=cfg.top_p,
        max_output_tokens=cfg.max_output_tokens,
    )
    return getattr(resp, "output_text", "") or ""


def evaluate_block(
    client: OpenAI,
    block: SourceBlock,
    cfg: RunConfig,
) -> Dict[str, Any]:
    """Evaluate a single SourceBlock and return a result dict."""

    code, was_truncated = truncate_code(block.code, cfg)

    prompt_vars = {
        "id": block.id,
        "file_path": block.file_path,
        "startline": block.startline,
        "endline": block.endline,
        "code": code,
    }
    prompt = fill_prompt(EVAL_PROMPT_V1, prompt_vars)

    # API call with retries on transient errors
    raw = ""
    for attempt in range(1, cfg.api_retries + 1):
        try:
            raw = call_model(client, prompt, cfg)
            break
        except Exception as e:
            if attempt == cfg.api_retries:
                raise
            backoff_sleep(attempt, cfg)

    # JSON parse + schema validation with repair retries
    parsed: Optional[Dict[str, Any]] = None
    parse_err: Optional[Exception] = None
    for jtry in range(cfg.json_retries + 1):
        try:
            parsed = extract_json_object(raw)
            validate_output_schema(parsed)
            break
        except Exception as e:
            parse_err = e
            if jtry == cfg.json_retries:
                break
            # Ask the model for a corrected JSON-only response
            repair_prompt = (
                "The following output is not valid JSON or does not match the required schema. "
                "Return the corrected output as VALID JSON ONLY — no markdown, no commentary.\n\n"
                "BROKEN OUTPUT:\n" + raw
            )
            raw = call_model(client, repair_prompt, cfg)

    if parsed is None:
        return {
            "id": block.id,
            "error": {
                "type": "parse_or_schema_error",
                "message": str(parse_err) if parse_err else "unknown",
                "raw_output": raw[:5000],
            },
            "model": cfg.model,
            "prompt_version": cfg.prompt_version,
            "run_settings": {
                "temperature": cfg.temperature,
                "top_p": cfg.top_p,
                "max_output_tokens": cfg.max_output_tokens,
            },
            "timestamp_utc": utc_now_iso(),
        }

    # Patch flags for truncation
    flags = parsed.get("overall", {}).get("flags", [])
    if not isinstance(flags, list):
        flags = []
    if was_truncated and "truncated_input" not in flags:
        flags.append("truncated_input")
    parsed["overall"]["flags"] = flags

    # Recompute solid_score for consistency
    try:
        solid_score = (
            int(parsed["srp"]["score"])
            + int(parsed["ocp"]["score"])
            + int(parsed["dip"]["score"])
        )
        parsed["overall"]["solid_score"] = solid_score
    except Exception:
        pass

    return {
        "id": block.id,
        "file_path": block.file_path,
        "startline": block.startline,
        "endline": block.endline,
        "srp": parsed["srp"],
        "ocp": parsed["ocp"],
        "dip": parsed["dip"],
        "overall": parsed["overall"],
        "model": cfg.model,
        "prompt_version": cfg.prompt_version,
        "run_settings": {
            "temperature": cfg.temperature,
            "top_p": cfg.top_p,
            "max_output_tokens": cfg.max_output_tokens,
        },
        "timestamp_utc": utc_now_iso(),
    }

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Parse <source> blocks from an XML-like file and evaluate each "
            "Java method against SRP/OCP/DIP via the OpenAI Responses API."
        ),
    )
    p.add_argument(
        "--input", required=True,
        help="Path to the input file containing <source> blocks.",
    )
    p.add_argument(
        "--output", default=None,
        help="Path to output JSONL file. If omitted, auto-derives from input (e.g., JHotDraw_SOLID_Eval.jsonl).",
    )
    p.add_argument(
        "--test-one", action="store_true",
        help="Evaluate only one method and print JSON result to stdout.",
    )
    p.add_argument(
        "--list", action="store_true",
        help="List all parsed blocks and exit (no API calls needed).",
    )
    p.add_argument(
        "--index", type=int, default=None,
        help="0-based index of the method to evaluate (used with --test-one).",
    )
    p.add_argument(
        "--id", default=None,
        help='Select method by id "file:start-end" (used with --test-one).',
    )
    p.add_argument("--resume", action="store_true", help="Skip ids already in output JSONL.")
    p.add_argument("--model", default="gpt-5.2", help="OpenAI model name.")
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--top-p", type=float, default=1.0)
    p.add_argument("--max-output-tokens", type=int, default=700)
    p.add_argument("--max-code-chars", type=int, default=14000)
    p.add_argument("--trunc-head-chars", type=int, default=9000)
    p.add_argument("--trunc-tail-chars", type=int, default=3000)
    p.add_argument("--api-retries", type=int, default=4)
    p.add_argument("--json-retries", type=int, default=2)
    p.add_argument("--base-backoff-s", type=float, default=1.0)
    p.add_argument("--max-backoff-s", type=float, default=20.0)
    return p.parse_args()

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    # Read input file first (needed for --list which requires no API key)
    with open(args.input, "r", encoding="utf-8") as f:
        raw_text = f.read()

    blocks = parse_source_blocks(raw_text)
    if not blocks:
        print("ERROR: No <source> blocks found in input file.", file=sys.stderr)
        sys.exit(1)
    print(f"[info] Parsed {len(blocks)} <source> blocks.", file=sys.stderr)

    # ---- list mode (no API key needed) ----
    if args.list:
        for i, b in enumerate(blocks):
            lines = b.endline - b.startline + 1
            preview = b.code.strip().split("\n")[0][:80]
            print(f"  [{i:4d}] {b.id}  ({lines} lines)  {preview}")
        print(f"\nTotal: {len(blocks)} blocks")
        return

    # Auto-derive output path if not given and not in test-one mode
    if args.output is None and not args.test_one:
        args.output = derive_output_path(args.input)
        print(f"[info] Auto-derived output: {args.output}", file=sys.stderr)

    # Validate that at least one mode is selected
    if not args.test_one and args.output is None:
        print(
            "ERROR: Provide --output for full-run mode, use --test-one, or use --list.",
            file=sys.stderr,
        )
        sys.exit(2)

    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY env var not set.", file=sys.stderr)
        sys.exit(2)

    cfg = RunConfig(
        input_path=args.input,
        output_path=args.output or "",
        model=args.model,
        resume=args.resume,
        temperature=args.temperature,
        top_p=args.top_p,
        max_output_tokens=args.max_output_tokens,
        max_code_chars=args.max_code_chars,
        trunc_head_chars=args.trunc_head_chars,
        trunc_tail_chars=args.trunc_tail_chars,
        api_retries=args.api_retries,
        json_retries=args.json_retries,
        base_backoff_s=args.base_backoff_s,
        max_backoff_s=args.max_backoff_s,
    )

    client = OpenAI()

    # ---- test-one mode ----
    if args.test_one:
        block: Optional[SourceBlock] = None

        if args.id is not None:
            # Select by id
            for b in blocks:
                if b.id == args.id:
                    block = b
                    break
            if block is None:
                print(f"ERROR: No block with id '{args.id}' found.", file=sys.stderr)
                print("[available ids]", file=sys.stderr)
                for b in blocks[:20]:
                    print(f"  {b.id}", file=sys.stderr)
                sys.exit(1)
        else:
            # Select by index (default 0)
            idx = args.index if args.index is not None else 0
            if idx < 0 or idx >= len(blocks):
                print(
                    f"ERROR: Index {idx} out of range (0..{len(blocks) - 1}).",
                    file=sys.stderr,
                )
                sys.exit(1)
            block = blocks[idx]

        # Print selected method metadata + code to stderr for inspection
        print("=" * 60, file=sys.stderr)
        print(f"  id        : {block.id}", file=sys.stderr)
        print(f"  file_path : {block.file_path}", file=sys.stderr)
        print(f"  startline : {block.startline}", file=sys.stderr)
        print(f"  endline   : {block.endline}", file=sys.stderr)
        print("-" * 60, file=sys.stderr)
        print(block.code, file=sys.stderr)
        print("=" * 60, file=sys.stderr)

        result = evaluate_block(client, block, cfg)
        # JSON result to stdout
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    # ---- full run mode ----
    assert args.output is not None

    processed: Set[str] = set()
    if cfg.resume:
        processed = load_processed_ids(cfg.output_path)
        print(
            f"[resume] {len(processed)} ids already in {cfg.output_path}",
            file=sys.stderr,
        )

    n_done = 0
    n_skipped = 0
    n_failed = 0

    for i, block in enumerate(blocks):
        if cfg.resume and block.id in processed:
            n_skipped += 1
            continue

        try:
            result = evaluate_block(client, block, cfg)
            append_jsonl(cfg.output_path, result)

            if "error" in result:
                n_failed += 1
                print(f"[fail] {block.id}", file=sys.stderr)
            else:
                n_done += 1
                if n_done % 20 == 0:
                    print(
                        f"[progress] done={n_done} failed={n_failed} "
                        f"skipped={n_skipped} / {len(blocks)}",
                        file=sys.stderr,
                    )

            if cfg.resume:
                processed.add(block.id)

        except Exception as e:
            n_failed += 1
            err_rec = {
                "id": block.id,
                "error": {"type": "exception", "message": str(e)},
                "model": cfg.model,
                "prompt_version": cfg.prompt_version,
                "timestamp_utc": utc_now_iso(),
            }
            append_jsonl(cfg.output_path, err_rec)
            print(f"[exception] {block.id}: {e}", file=sys.stderr)

    summary = {
        "total_blocks": len(blocks),
        "processed_ok": n_done,
        "processed_failed": n_failed,
        "skipped": n_skipped,
        "output_path": cfg.output_path,
        "timestamp_utc": utc_now_iso(),
    }
    print(json.dumps(summary, indent=2), file=sys.stderr)


if __name__ == "__main__":
    main()
