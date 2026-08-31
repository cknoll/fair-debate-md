"""
Command line interface for fair_debate_md
"""

import argparse
from . import core
from . import debate_builder
from .release import __version__

from ipydex import IPS, activate_ips_on_exception


def main():

    # docs: https://docs.python.org/3/library/argparse.html
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    # parser.add_argument("cmd", help=f"main command")
    subparsers = parser.add_subparsers(dest="cmd", help="")

    parser_a = subparsers.add_parser("unpack-repos", help="unpack repos from fixtures")
    parser_a.add_argument("target_dir", type=str, help="target dir to unpack repos to")
    parser_c = subparsers.add_parser(
        "build-debate-repo",
        help="build a content repo from a debate written as a single md file",
    )
    parser_c.add_argument("source", type=str, help="the md file holding the whole debate")
    parser_c.add_argument(
        "--patches-into",
        metavar="DIR",
        type=str,
        help="where to write the patch collection (default: ./<debate_key>/patches_01)",
    )
    parser_c.add_argument(
        "--repo-into",
        metavar="DIR",
        type=str,
        help="keep the built repo here instead of building it in a temporary dir",
    )
    parser_c.add_argument(
        "--into-fixtures",
        action="store_true",
        help="write the patches into the fixture dir of the installed fair_debate_md "
        "(this is how a fixture debate is updated)",
    )

    args = parser.parse_args()

    if args.cmd == "unpack-repos":
        core.unpack_repos(args.target_dir)
    elif args.cmd == "build-debate-repo":
        debate_builder.build_debate_repo(
            args.source,
            patches_into=args.patches_into,
            repo_into=args.repo_into,
            into_fixtures=args.into_fixtures,
        )
    else:
        print("nothing to do, see option `--help` for more info")
