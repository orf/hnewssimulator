"""
hnews-fetcher.

Usage:
    hnews-fetcher [<data-type>...] [--from=<id> --to=<id>] [--conns=<count>]

Options:
    --conns=<count> Number of concurrent connections [default: 50].
    --new-items     Only show new comments/stories (not updated/edited ones).
    --from=<id>     Fetch ID's from this ID.
    --to=<id>       Fetch ID's to this ID.
"""

import docopt
import asyncio
import requests
import json
from hnews_fetcher.scrape import get_items

event_loop = asyncio.get_event_loop()


def run():
    arguments = docopt.docopt(__doc__)

    data_types = set(arguments["<data-type>"])
    from_id = arguments["--from"]
    to_id = arguments["--to"]
    conn_count = arguments["--conns"]

    if not data_types:
        data_types = {"all"}

    def output(data):
        print(json.dumps(data))

    if to_id is None:
        to_id = requests.get("https://hacker-news.firebaseio.com/v0/maxitem.json").json()
    else:
        to_id = int(to_id)

    if from_id is None:
        from_id = 1
    else:
        from_id = int(from_id)

    if conn_count is None:
        conn_count = 50
    else:
        conn_count = int(conn_count)

    event_loop.run_until_complete(
        get_items(data_types, output, to_id, from_id=from_id, max_requests=conn_count)
    )


if __name__ == "__main__":
    run()
