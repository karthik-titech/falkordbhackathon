"""Load graph seeds or serve the demo, including stdlib-only offline replay."""

import argparse
import json
import os
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python3 -m warmopen.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    load = commands.add_parser("load", help="Load a seed into FalkorDB")
    load.add_argument("seed", type=Path)
    attendance = commands.add_parser("import-attendees", help="Import a conference attendance manifest")
    attendance.add_argument("file", type=Path)
    attendance.add_argument("--check", action="store_true", help="Validate and count without writing")
    serve = commands.add_parser("serve", help="Serve the requester and owner pages")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8080)
    serve.add_argument("--public-trial", action="store_true",
                        help="Show the public conference landing page at /")
    modes = serve.add_mutually_exclusive_group()
    modes.add_argument("--record", type=Path, metavar="DIR")
    modes.add_argument("--replay", type=Path, metavar="DIR")
    args = parser.parse_args(argv)

    if args.command == "import-attendees":
        from .attendance_import import import_attendees, read_manifest
        from .graphstore import GraphStore

        try:
            manifest = read_manifest(args.file)
            store = GraphStore.connect()
            counts = import_attendees(store, manifest, check=args.check)
        except Exception:
            parser.error("Attendance import failed")
        print(json.dumps(counts, sort_keys=True))
        return

    if args.command == "serve" and args.replay:
        from .app import make_server

        if not args.replay.is_dir():
            parser.error("Replay directory does not exist")
        server = make_server(None, args.host, args.port, mode="recorded",
                             recordings_dir=args.replay,
                             public_landing=args.public_trial)
    else:
        from .graphstore import GraphStore

        store = GraphStore.connect()
        if args.command == "load":
            from .seed import load_seed

            print(json.dumps(load_seed(store, json.loads(args.seed.read_text(encoding="utf-8"))), sort_keys=True))
            return
        from .app import make_server
        from .decisions import decisions_client
        from .llm import anthropic_llm

        decision_key = os.environ.get("DECISIONS_API_KEY")
        llm_key = os.environ.get("ANTHROPIC_API_KEY")
        jev = decisions_client(decision_key) if decision_key else None
        llm = anthropic_llm(llm_key) if llm_key else None
        server = make_server(store, args.host, args.port, jev=jev, llm=llm,
                             record_dir=args.record, public_landing=args.public_trial)
    mode = "Recorded run" if args.replay else "Live run"
    print(f"{mode}: http://{args.host}:{server.server_address[1]}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
