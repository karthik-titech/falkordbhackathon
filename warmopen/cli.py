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
    serve = commands.add_parser("serve", help="Serve the requester and owner pages")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8080)
    modes = serve.add_mutually_exclusive_group()
    modes.add_argument("--record", type=Path, metavar="DIR")
    modes.add_argument("--replay", type=Path, metavar="DIR")
    args = parser.parse_args(argv)

    from .app import make_server

    if args.command == "serve" and args.replay:
        if not args.replay.is_dir():
            parser.error("Replay directory does not exist")
        server = make_server(None, args.host, args.port, mode="recorded",
                             recordings_dir=args.replay)
    else:
        from .graphstore import GraphStore

        store = GraphStore.connect()
        if args.command == "load":
            from .seed import load_seed

            print(json.dumps(load_seed(store, json.loads(args.seed.read_text(encoding="utf-8"))), sort_keys=True))
            return

        from .jev import jev_client
        from .llm import anthropic_llm

        jev_key = os.environ.get("TYPESAFE_JEV_API_KEY")
        llm_key = os.environ.get("ANTHROPIC_API_KEY")
        jev = jev_client(jev_key) if jev_key else None
        llm = anthropic_llm(llm_key) if llm_key else None
        server = make_server(store, args.host, args.port, jev=jev, llm=llm, record_dir=args.record)
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
