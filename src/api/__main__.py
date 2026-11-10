import argparse

import uvicorn

from api.main import create_app

parser = argparse.ArgumentParser(prog="python -m api", description="SafeSight API")
parser.add_argument("--host", default="127.0.0.1")
parser.add_argument("--port", type=int, default=8000)
args = parser.parse_args()
uvicorn.run(create_app(), host=args.host, port=args.port)
