#!/usr/bin/env python3
"""Compatibility entry point for rvw cov fp. Inputs need complete C1 evidence."""
import sys
from rvw.cli import main

if __name__=='__main__':
    raise SystemExit(main(['cov','fp',*sys.argv[1:]]))
