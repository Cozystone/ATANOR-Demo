from __future__ import annotations

import argparse
import os
import sys

import uvicorn

from app.services.desktop_paths import configure_desktop_data_dir


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Homage FastAPI desktop sidecar")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--log-level", default=os.getenv("HOMAGE_LOG_LEVEL", "info"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    data_dir = configure_desktop_data_dir(args.data_dir, chdir=True)
    os.environ["HOMAGE_DESKTOP_SIDECAR"] = "1"
    print(f"HOMAGE_API_READY port={args.port} data_dir={data_dir}", flush=True)
    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        log_level=args.log_level,
        access_log=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
