"""
Command line interface for fair_debate_md
"""

import argparse
from . import core

from ipydex import IPS, activate_ips_on_exception


def main():

    # docs: https://docs.python.org/3/library/argparse.html
    parser = argparse.ArgumentParser()
    # parser.add_argument("cmd", help=f"main command")
    subparsers = parser.add_subparsers(dest="cmd", help="")

    parser_a = subparsers.add_parser("unpack-repos", help="unpack repos from fixtures")
    parser_a.add_argument("target_dir", type=str, help="target dir to unpack repos to")
    # parser_b = subparsers.add_parser("unused-subcommand", help="")
    # parser_b.add_argument("target_dir2", type=str, help="target dir to unpack repos to")

    args = parser.parse_args()

    if args.cmd == "unpack-repos":
        core.unpack_repos(args.target_dir)
    else:
        print("nothing to do, see option `--help` for more info")
