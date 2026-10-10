"""Prevent accidental public commits of secrets or raw market archives."""
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
FORBIDDEN_SUFFIX={".p8",".p12",".pfx",".pem",".key",".db",".parquet",".sqlite",".csv"}
FORBIDDEN_PARTS={".secrets",".credentials","secrets","output","storage","results"}
PATTERNS=[
    re.compile(rb"AKIA[0-9A-Z]{16}"),
    re.compile(rb"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(rb"-----BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY-----"),
    re.compile(rb"sk-[A-Za-z0-9]{32,}"),
    re.compile(rb"(?i)(?:api[_-]?key|secret[_-]?key|access[_-]?token)\s*[:=]\s*[\"'][a-z0-9_\-/+=]{18,}[\"']"),
]
def check():
    raw=subprocess.check_output(["git","diff","--cached","--name-only","-z"],cwd=ROOT)
    names=[x.decode() for x in raw.split(b"\x00") if x]
    errors=[]
    for name in names:
        path=Path(name)
        if path.suffix.lower() in FORBIDDEN_SUFFIX or set(path.parts)&FORBIDDEN_PARTS or name.startswith(".env"):
            errors.append(f"forbidden path: {name}")
            continue
        blob=subprocess.check_output(["git","show",":"+name],cwd=ROOT)
        if len(blob)>12*1024*1024:
            errors.append(f"oversized staged file: {name}")
        if any(p.search(blob) for p in PATTERNS):
            errors.append(f"possible credential: {name}")
    print(f"PUBLIC_GIT_SAFETY scanned={len(names)} suspicious={len(errors)}")
    for err in errors:print("BLOCKED",err)
    return 1 if errors else 0

if __name__=="__main__":sys.exit(check())
