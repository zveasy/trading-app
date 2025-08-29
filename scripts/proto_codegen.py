from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    from grpc_tools import protoc  # type: ignore
except Exception:
    print("grpcio-tools not installed. Install with: pip install grpcio-tools")
    sys.exit(1)

ROOT = Path(__file__).resolve().parents[1]
PROTO_DIRS = [ROOT / "shared_proto", ROOT / "proto"]
OUT_DIR = ROOT / "shared_proto"

# Ensure package init
(OUT_DIR / "__init__.py").write_text("# generated package\n", encoding="utf-8")

protos = []
for d in PROTO_DIRS:
    if d.exists():
        for p in d.glob("*.proto"):
            protos.append(str(p))

if not protos:
    print("No .proto files found.")
    sys.exit(0)

args = [
    "protoc",
    f"-I{ROOT}",
    f"-I{ROOT / 'shared_proto'}",
    f"-I{ROOT / 'proto'}",
    f"--python_out={OUT_DIR}",
]
args.extend(protos)

print("Running:", " ".join(args))
rc = protoc.main(args)
if rc != 0:
    print("protoc failed with exit code", rc)
    sys.exit(rc)
print("Protobufs generated under", OUT_DIR)
