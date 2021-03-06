import json
import pathlib
import shutil
import random
import random
import jinja2
import unicodedata

with open("data/posts.json", "r") as fd:
    posts = json.load(fd)

template = jinja2.FileSystemLoader("template/").load(jinja2.Environment(), "index.jinja2")
comment_template = jinja2.FileSystemLoader("template/").load(jinja2.Environment(), "comments.jinja2")

dist = pathlib.Path("dist")
comments = dist / "comments"
if not dist.exists():
    dist.mkdir()

if not comments.exists():
    comments.mkdir()


def render_section(name, posts):
    # Split the pages into chunks of 30 and reverse them, because we want newly generated posts to be at the top.
    reversed_posts = list(reversed(posts))
    page_chunks = list([reversed_posts[x:x + 30] for x in range(0, len(posts), 30)])

    for i, chunk in enumerate(page_chunks):
        file_name = "{0}_{1}.html".format(name, i) if i != 0 else "{0}.html".format(name)
        is_last = len(page_chunks) == i + 1

        random.shuffle(chunk)

        with (dist / file_name).open("wb") as fd:
            txt = template.render(posts=chunk, idx=i, is_last=is_last, rand=random.randint)
            fd.write(unicodedata.normalize("NFC", txt).encode("utf8"))


ask_hn = [post for post in posts if post["type"] == "ask"]
show_hn = [post for post in posts if post["type"] == "show"]

render_section("index", posts)
render_section("ask", ask_hn)
render_section("show", show_hn)

for post in posts:
    with (dist / "comments" / "comments_{0}.html".format(post["id"])).open("wb") as fd:
        txt = comment_template.render(post=post, rand=random.randint)
        fd.write(unicodedata.normalize("NFC", txt).encode("utf8"))

news = dist / "news.css"
if not news.exists():
    shutil.copy(
        "template/news.css",
        str(news)
    )
