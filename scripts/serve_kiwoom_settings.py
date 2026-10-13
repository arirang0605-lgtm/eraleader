#!/usr/bin/env python3
"""Serve EraLeader's separate DEMO/REAL Kiwoom read-only settings, Mac loopback."""
from pathlib import Path
import argparse
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from eraleader.kiwoom_profile_settings import serve

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port",type=int,default=8782)
    args=parser.parse_args()
    print("KIWOOM_SETTINGS_LOCAL_URL=http://127.0.0.1:%s/" % args.port, flush=True)
    serve(port=args.port)
if __name__=="__main__":
    main()
