import argparse
import logging

from unga_speeches.build import dataset, release, session
from unga_speeches.sources import ungdc, verbatim


def main() -> None:
    parser = argparse.ArgumentParser(prog="unga", description="UN General Assembly general debate pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    session_cmd = sub.add_parser("session", help="scrape, extract and render one session from gadebate.un.org (64 onwards)")
    session_cmd.add_argument("session", type=int)
    session_cmd.add_argument("--refresh", action="store_true", help="re-download files already cached")
    session_cmd.add_argument(
        "--refresh-pages",
        action="store_true",
        help="re-download the sitemap and speaker pages only, to pick up new speeches and transcripts",
    )
    session_cmd.add_argument("--only", nargs="+", help="limit to these delegation slugs, skipping the dataset and report")

    sub.add_parser("history", help="merge the UN General Debate Corpus (1946 onwards) with its speaker list")

    site = sub.add_parser("site", help="write one session's analysis page to site/ (needs the analysis dependency group)")
    site.add_argument("session", type=int)

    news = sub.add_parser("news", help="download the news reports listed for a session and extract the UN coverage on each speaker page")
    news.add_argument("session", type=int)

    sub.add_parser("brands", help="download the Digital News Report's biggest online news brands in each market")

    leanings = sub.add_parser("leanings", help="refresh each sampled outlet's political leaning and record changes in its history")
    leanings.add_argument("session", type=int)

    scans = sub.add_parser("scanned", help="split the UN's scanned verbatim records of sessions 1 to 47 (1946-1992) into speeches")
    scans.add_argument("sessions", type=int, nargs="+")

    sub.add_parser("release", help="package the tables and speech pages into dist/ for a data release")
    sub.add_parser("dataset", help="combine the corpus, the verbatim records and gadebate into one table")

    records = sub.add_parser("verbatim", help="split the UN verbatim records of one or more sessions (48 onwards) into speeches")
    records.add_argument("sessions", type=int, nargs="+")

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.command == "session":
        speeches = session.run_session(
            args.session, refresh=args.refresh, only=set(args.only) if args.only else None, refresh_pages=args.refresh_pages
        )
        logging.info("built %d speeches", len(speeches))
    elif args.command == "verbatim":
        for s in args.sessions:
            logging.info("wrote %s", verbatim.build_session(s))
    elif args.command == "site":
        from unga_speeches.analysis import site as analysis_site

        logging.info("wrote %s", analysis_site.build(args.session))
    elif args.command == "news":
        from unga_speeches.sources import news as news_source

        logging.info("wrote %s", news_source.build(args.session))
        logging.info("wrote %s", news_source.coverage(args.session))
    elif args.command == "brands":
        from unga_speeches.sources import dnr

        logging.info("wrote %s", dnr.build())
    elif args.command == "leanings":
        from unga_speeches.sources import leaning

        logging.info("wrote %s", leaning.build(args.session))
    elif args.command == "scanned":
        from unga_speeches.sources import scanned

        after = 1
        for number in sorted(args.sessions):
            out, last = scanned.build_session(number, after=after)
            after = last + 1 if number < scanned.FIRST_SESSION_NUMBERED else 1
            logging.info("wrote %s", out)
    elif args.command == "release":
        logging.info("wrote %s", release.package())
    elif args.command == "dataset":
        logging.info("wrote %s", dataset.build())
    elif args.command == "history":
        logging.info("wrote %s", ungdc.build_history())


if __name__ == "__main__":
    main()
