"""Command-line entry point for sfit.

    sfit fit     transient.csv [-o params.json]          TCAD current -> double-exp params
    sfit gen     circuit.sp --node N --params params.json  inject strike, write SPICE deck
    sfit charge  --let 10 --depth 2                       LET -> deposited charge
    sfit inspect deck.sp [--json]                         summarize a SPICE deck
    sfit diff    ref.sp ours.sp                           compare two decks structurally
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence

from sfit import __version__, spice, tcad


def _load_params(args) -> tcad.DoubleExp:
    if args.params:
        d = json.loads(Path(args.params).read_text())
        return tcad.DoubleExp(d["q"], d["tau_r"], d["tau_f"], d.get("t0", 0.0))
    if args.transient:
        return tcad.fit_double_exp(*tcad.load_transient(args.transient))
    q = args.q if args.q is not None else tcad.let_to_charge(args.let, args.depth)
    return tcad.DoubleExp(q, args.tau_r, args.tau_f, args.t0)


def cmd_fit(args) -> int:
    t, i = tcad.load_transient(args.transient, args.time_col, args.current_col)
    p = tcad.fit_double_exp(t, i)
    out = p.to_dict()
    out["q_integrated"] = tcad.collected_charge(t, i)
    text = json.dumps(out, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n")
    print(text)
    return 0


def cmd_gen(args) -> int:
    p = _load_params(args)
    deck = spice.inject(Path(args.netlist).read_text(), args.node, p, style=args.style,
                        t_stop=args.tstop, ground=args.ground)
    if args.output:
        Path(args.output).write_text(deck)
    else:
        sys.stdout.write(deck)
    return 0


def cmd_charge(args) -> int:
    q = tcad.let_to_charge(args.let, args.depth)
    print(f"Q = {q:.6g} C ({q * 1e15:.4g} fC)")
    return 0


def cmd_inspect(args) -> int:
    s = spice.parse_file(args.deck).summary()
    if args.json:
        print(json.dumps(s, indent=2))
        return 0
    print(f"title: {s['title']}")
    print(f"elements: {s['element_counts']}")
    print(f"nodes ({len(s['nodes'])}): {' '.join(s['nodes'])}")
    for src in s["sources"]:
        print(f"source {src['name']} {' '.join(src['nodes'])}: {src['value']}")
    for name, body in s["models"].items():
        print(f"model {name}: {body}")
    for d in s["directives"]:
        print(f"directive: {d}")
    return 0


def cmd_diff(args) -> int:
    a, b = spice.parse_file(args.ref).summary(), spice.parse_file(args.ours).summary()
    same = True
    for key in ("element_counts", "nodes", "models", "subckts"):
        if a[key] != b[key]:
            same = False
            print(f"[{key}]\n  ref : {a[key]}\n  ours: {b[key]}")
    sa = {s["name"].lower(): s for s in a["sources"]}
    sb = {s["name"].lower(): s for s in b["sources"]}
    for n in sorted(sa.keys() | sb.keys()):
        if sa.get(n) != sb.get(n):
            same = False
            print(f"[source {n}]\n  ref : {sa.get(n)}\n  ours: {sb.get(n)}")
    print("identical structure" if same else "")
    return 0 if same else 1


def _pulse_args(p):
    g = p.add_argument_group("pulse (pick one: --params, --transient, or explicit values)")
    g.add_argument("--params", help="JSON from `sfit fit`")
    g.add_argument("--transient", help="TCAD transient CSV to fit on the fly")
    g.add_argument("--q", type=float, help="charge [C]")
    g.add_argument("--let", type=float, default=1.0, help="LET [MeV*cm^2/mg] if --q not given")
    g.add_argument("--depth", type=float, default=1.0, help="collection depth [um]")
    g.add_argument("--tau-r", type=float, default=5e-12)
    g.add_argument("--tau-f", type=float, default=50e-12)
    g.add_argument("--t0", type=float, default=0.0)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="sfit", description="TCAD -> SPICE strike model toolkit")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("fit", help="fit double-exponential to a TCAD current transient")
    p.add_argument("transient")
    p.add_argument("--time-col", type=int, default=0)
    p.add_argument("--current-col", type=int, default=1)
    p.add_argument("-o", "--output")
    p.set_defaults(func=cmd_fit)

    p = sub.add_parser("gen", help="inject a strike current into a SPICE netlist")
    p.add_argument("netlist")
    p.add_argument("--node", required=True)
    p.add_argument("--ground", default="0")
    p.add_argument("--style", choices=["exp", "pwl"], default="exp")
    p.add_argument("--tstop", type=float)
    p.add_argument("-o", "--output")
    _pulse_args(p)
    p.set_defaults(func=cmd_gen)

    p = sub.add_parser("charge", help="LET and depth -> deposited charge")
    p.add_argument("--let", type=float, required=True)
    p.add_argument("--depth", type=float, required=True)
    p.set_defaults(func=cmd_charge)

    p = sub.add_parser("inspect", help="summarize a SPICE deck")
    p.add_argument("deck")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_inspect)

    p = sub.add_parser("diff", help="structural diff of two SPICE decks")
    p.add_argument("ref")
    p.add_argument("ours")
    p.set_defaults(func=cmd_diff)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
