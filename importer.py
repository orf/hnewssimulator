from sqlalchemy import create_engine
from db import Base
import json
from datetime import datetime
import csv
from urllib.parse import urlparse
import re

TAG_RE = re.compile(r'<[^>]+>')

engine = create_engine("postgresql://hnews:hnews@localhost/hnews")
Base.metadata.create_all(engine)

seen_ids = set()

with open("data/data", "r") as inp, \
        open("data/posts.csv", "w", newline="", encoding="utf8") as posts_fd, \
        open("data/comments.csv", "w", newline="", encoding="utf8") as comments_fd:
    comments_out = csv.writer(comments_fd)
    posts_out = csv.writer(posts_fd)

    for i, line in enumerate(inp):
        try:
            parsed = json.loads(line.strip())
        except Exception as e:
            continue

        if parsed.get("deleted", False):
            continue

        if parsed["id"] in seen_ids:
            print("!", end="")
            continue

        seen_ids.add(parsed["id"])

        if parsed["type"] in {"story", "job"}:

            if "title" not in parsed:
                continue

            title = parsed["title"]
            lowered = title.lower()

            is_ask, is_show, is_tell, is_job = False, False, False, False

            if lowered.startswith("ask hn") or lowered.startswith("ask yc") or lowered.startswith("as hn"):
                is_ask = True
            elif lowered.startswith("show hn"):
                is_show = True
            elif lowered.startswith("tell hn"):
                is_tell = True

            if parsed["type"] == "job":
                is_job = True

            text, url, host = None, None, None
            if "url" not in parsed:
                text = parsed.get("text", "")
            else:
                url = parsed["url"]
                host = urlparse(url).netloc.replace("www.", "")

            data = (parsed["id"],
                    title,
                    parsed["by"],
                    datetime.fromtimestamp(parsed["time"]),
                    text,
                    url,
                    host,
                    parsed["score"],
                    "{%s}" % ", ".join(str(x) for x in parsed.get("kids", [])),
                    parsed.get("dead", False),
                    parsed.get("descendants", 0),
                    None,
                    is_ask,
                    is_show,
                    is_tell,
                    is_job)
            posts_out.writerow(data)
        else:

            if "text" not in parsed:
                print("?", end="")
                continue

            txt = TAG_RE.sub('', parsed["text"]).replace("\x00", "")

            data = (
                parsed["id"],
                parsed["by"],
                datetime.fromtimestamp(parsed["time"]).isoformat(),
                txt,
                "{%s}" % ", ".join(str(x) for x in parsed.get("kids", [])),
                parsed["parent"],
                parsed.get("dead", False)
            )
            comments_out.writerow(data)

