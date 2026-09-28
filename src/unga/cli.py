import argparse
import logging

from . import dataset, pipeline, ungdc, verbatim


def main() -> None:
    parser = argparse.ArgumentParser(prog="unga", description="UN General Assembly general debate pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    session = sub.add_parser("session", help="scrape, extract and render one session from gadebate.un.org (64 onwards)")
    session.add_argument("session", type=int)
    session.add_argument("--refresh", action="store_true", help="re-download files already cached")
    session.add_argument("--refresh-pages", action="store_true", help="re-download the sitemap and speaker pages only, to pick up new speeches and transcripts")
    session.add_argument("--only", nargs="+", help="limit to these delegation slugs, skipping the dataset and report")

    sub.add_parser("history", help="merge the UN General Debate Corpus (1946 onwards) with its speaker list")

    sub.add_parser("dataset", help="combine the corpus, the verbatim records and gadebate into one table")

    records = sub.add_parser("verbatim", help="split the UN verbatim records of one or more sessions (48 onwards) into speeches")
    records.add_argument("sessions", type=int, nargs="+")

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.command == "session":
        speeches = pipeline.run_session(args.session, refresh=args.refresh, only=set(args.only) if args.only else None, refresh_pages=args.refresh_pages)
        logging.info("built %d speeches", len(speeches))
    elif args.command == "verbatim":
        for s in args.sessions:
            logging.info("wrote %s", verbatim.build_session(s))
    elif args.command == "dataset":
        logging.info("wrote %s", dataset.build())
    elif args.command == "history":
        logging.info("wrote %s", ungdc.build_history())


if __name__ == "__main__":
    main()
