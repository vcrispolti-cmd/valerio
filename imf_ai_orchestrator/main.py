"""IMF multi-model analytical orchestrator v1.1 — command line.

Examples
  # Dry run on the synthetic sample case (no model is contacted)
  python main.py run --case evaluation/cases/sample_case --level 3 --mode mock \
      --question "What explains the decline in Country A's energy-sector arrears?" --as-of 2026-09-30

  # Manual mode: prompts are written to runs/<id>/manual/; paste each into the
  # named chatbot, save the reply next to it, then resume
  python main.py run --mode manual --confidentiality PUBLIC --question "..." --document-type policy_note
  python main.py resume <run_id>

  # Show which model gets which role under the current constraints
  python main.py roles --confidentiality PUBLIC --mode live

  # Audit any draft against an approved register (claim-strengthening check)
  python main.py audit-draft --state runs/<id>/state.json --draft my_draft.md

  # Planted-error benchmark: measure what each control catches
  python main.py evaluate --case evaluation/cases/sample_case --n 200 --seed 7
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from orchestrator import roles, security  # noqa: E402
from orchestrator.agents import PendingManual  # noqa: E402
from orchestrator.config import load_config  # noqa: E402
from orchestrator.model import Claim  # noqa: E402
from orchestrator.pipeline import Pipeline, StopRun  # noqa: E402
from orchestrator.strength import audit_draft  # noqa: E402

DOC_TYPES = ["analytical_question", "selected_issues_paper", "staff_report", "policy_note"]


def cmd_run(args, spec=None):
    cfg = load_config(ROOT)
    if spec is None:
        run_id = args.run_id or f"IMF-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}"
        spec = {"run_id": run_id, "question": args.question, "document_type": args.document_type,
                "level": args.level, "confidentiality": args.confidentiality, "mode": args.mode,
                "country": args.country, "as_of": args.as_of, "context": args.context,
                "case_dir": str(Path(args.case).resolve()) if args.case else None,
                "documents_dir": str(Path(args.documents_dir).resolve()) if args.documents_dir else None,
                "data_csv": [str(Path(p).resolve()) for p in args.data_csv],
                "rotation_seed": args.rotation_seed}
    run_dir = ROOT / "runs" / spec["run_id"]
    run_dir.mkdir(parents=True, exist_ok=True)
    pipe = Pipeline(cfg, run_dir, spec)
    try:
        st = pipe.run()
    except PendingManual as p:
        print(f"Run {spec['run_id']}: waiting for {len(p.paths)} manual reply(ies).")
        for path in p.paths:
            print(f"  paste {path.relative_to(ROOT)}  ->  save reply as {path.name.replace('.prompt.md', '.reply.md')}")
        print(f"Then: python main.py resume {spec['run_id']}")
        return 2
    except StopRun as s:
        print(f"STOPPED: {s}")
        return 3
    last = st.gates.get("final_gate") or st.gates.get("gate") or {}
    print(f"Run {st.run_id}: level {st.level} ({'; '.join(st.level_basis)})")
    print(f"Status: {last.get('status', 'n/a')}  score {last.get('score', 'n/a')}  "
          f"automatic REDs: {len(last.get('automatic_reds', []))}")
    for n in st.notes:
        print(f"  note: {n}")
    print(f"Dashboard: {(run_dir / '19_dashboard.md').relative_to(ROOT)}")
    return 0 if last.get("status") != "RED" else 1


def cmd_resume(args):
    spec = json.loads((ROOT / "runs" / args.run_id / "00_input.json").read_text(encoding="utf-8"))
    return cmd_run(args, spec)


def cmd_roles(args):
    cfg = load_config(ROOT)
    permitted = security.permitted_agents(cfg, args.confidentiality, args.mode)
    if not permitted:
        print(f"No model may be used for {args.confidentiality} material under config/confidentiality.yaml.")
        return 3
    a = roles.assign(cfg, permitted, args.rotation_seed)
    for role, agents in a.items():
        fams = ", ".join(f"{x} ({cfg.family(x)})" for x in agents)
        print(f"{role:22s} {fams}")
    return 0


def cmd_audit(args):
    cfg = load_config(ROOT)
    st = json.loads(Path(args.state).read_text(encoding="utf-8"))
    claims = {k: Claim.from_dict(v) for k, v in st["claims"].items()}
    recs = audit_draft(Path(args.draft).read_text(encoding="utf-8"), claims, cfg.strength)
    bad = [r for r in recs if r["findings"]]
    for r in bad:
        print(f"[{', '.join(r['red_codes']) or 'REVIEW'}] {r['tags'] or 'untagged'} {r['findings']}\n    {r['text']}")
    print(f"{len(recs)} sentences, {len(bad)} flagged, {sum(1 for r in bad if r['red_codes'])} blocking")
    return 1 if any(r["red_codes"] for r in bad) else 0


def cmd_evaluate(args):
    from evaluation.harness import run_benchmark
    report = run_benchmark(ROOT, Path(args.case), n=args.n, seed=args.seed, mode=args.mode,
                           reviewers=[r for r in args.reviewers.split(",") if r], confidentiality=args.confidentiality)
    print(report)
    return 0


def main():
    p = argparse.ArgumentParser(description="IMF multi-model analytical orchestrator v1.1")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="start a run")
    r.add_argument("--question", required=True)
    r.add_argument("--document-type", default="analytical_question", choices=DOC_TYPES)
    r.add_argument("--level", type=int, default=2, choices=range(5),
                   help="requested level; rules may raise it, never lower it")
    r.add_argument("--confidentiality", default="INTERNAL", choices=["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"])
    r.add_argument("--mode", default="mock", choices=["mock", "manual", "live"])
    r.add_argument("--case", help="case folder with sources/, data.csv and (for mock mode) mock/ fixtures")
    r.add_argument("--documents-dir", help="folder holding source documents referenced by local_path")
    r.add_argument("--data-csv", action="append", default=[], help="CSV extract(s): series,country,period,value")
    r.add_argument("--country", default="")
    r.add_argument("--as-of", default=datetime.now(timezone.utc).date().isoformat())
    r.add_argument("--context", default="")
    r.add_argument("--run-id")
    r.add_argument("--rotation-seed", type=int)
    r.set_defaults(fn=cmd_run)

    s = sub.add_parser("resume", help="resume a run (e.g. after pasting manual replies)")
    s.add_argument("run_id")
    s.set_defaults(fn=cmd_resume)

    ro = sub.add_parser("roles", help="show role assignments")
    ro.add_argument("--confidentiality", default="PUBLIC")
    ro.add_argument("--mode", default="live", choices=["mock", "manual", "live"])
    ro.add_argument("--rotation-seed", type=int)
    ro.set_defaults(fn=cmd_roles)

    a = sub.add_parser("audit-draft", help="check a draft against an approved claim register")
    a.add_argument("--state", required=True)
    a.add_argument("--draft", required=True)
    a.set_defaults(fn=cmd_audit)

    e = sub.add_parser("evaluate", help="planted-error benchmark")
    e.add_argument("--case", default=str(ROOT / "evaluation" / "cases" / "sample_case"))
    e.add_argument("--n", type=int, default=200)
    e.add_argument("--seed", type=int, default=7)
    e.add_argument("--mode", default="mock", choices=["mock", "live"])
    e.add_argument("--reviewers", default="", help="comma-separated agents to test as model reviewers (live mode)")
    e.add_argument("--confidentiality", default="PUBLIC")
    e.set_defaults(fn=cmd_evaluate)

    args = p.parse_args()
    sys.exit(args.fn(args))


if __name__ == "__main__":
    main()
