from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db import Base, Story, Comment
import json
from datetime import datetime
import sys
import csv
import io

engine = create_engine("postgresql://hnews:hnews@localhost/hnews")
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
sesh = Session()

with open("data.json", "r") as inp:
    posts_fd = open("posts.csv", "w", newline="", encoding="utf8")
    comments_fd = open("comments.csv", "w", newline="", encoding="utf8")

    comments_out = csv.writer(comments_fd)
    posts_out = csv.writer(posts_fd)

    for line in inp:
        try:
            parsed = json.loads(line.strip())
        except Exception as e:
            continue

        if parsed.get("deleted", False):
            continue

        if parsed["type"] == "story":
            if "by" not in parsed:
                continue

            title = parsed["title"]
            lowered = title.lower()

            is_ask, is_show = False, False

            if lowered.startswith("ask hn"):
                title = title[6:]
                title = title.lstrip(":").strip()
                is_ask = True
            elif lowered.startswith("show hn"):
                title = title[7:]
                title = title.lstrip(":").strip()
                is_show = True

            text, url = None, None
            if "url" not in parsed:
                text = parsed.get("text", "")
            else:
                url = parsed["url"]

            data = (parsed["id"],
                    title,
                    parsed["by"],
                    datetime.fromtimestamp(parsed["time"]),
                    text,
                    url,
                    parsed["score"],
                    "{%s}" % ", ".join(str(x) for x in parsed.get("kids", [])),
                    parsed.get("dead", False),
                    parsed.get("descendants", 0),
                    is_ask,
                    is_show)
            posts_out.writerow(data)
        else:

            data = (
                parsed["id"],
                parsed["by"],
                datetime.fromtimestamp(parsed["time"]).isoformat(),
                parsed["text"],
                "{%s}" % ", ".join(str(x) for x in parsed.get("kids", [])),
                parsed["parent"],
                parsed.get("dead", False)
            )
            comments_out.writerow(data)
