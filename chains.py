import io
import os
import random
import json
import pathlib
import itertools

from contexttimer import Timer
from sqlalchemy import create_engine
from sqlalchemy.sql import func
from sqlalchemy.orm import sessionmaker

from db import Base, Story, Comment
import markovify
import multiprocessing
import tempfile


class CommentSim(markovify.Text):
    def test_sentence_input(self, sentence):
        return True

    def _prepare_text(self, text):
        text = text.strip()
        if not text.endswith((".", "?", "!")):
            text += "."

        return text

    def sentence_split(self, text):
        # split everything up by newlines, prepare them, and join back together
        lines = text.splitlines()
        text = " ".join([self._prepare_text(line)
                         for line in lines if line.strip()])

        return markovify.split_into_sentences(text)


class SubmissionTitleSim(markovify.Text):
    def test_sentence_input(self, sentence):
        return True

    def sentence_split(self, text):
        return text.splitlines()


engine = create_engine("postgresql://hnews:hnews@localhost/hnews")
Base.metadata.create_all(engine)

queries = {
    "ask": {
        "query": {"is_ask": True},
        "count": 2
    },
    "tell": {
        "query": {"is_tell": True},
        "count": 1
    },
    "show": {
        "query": {"is_show": True},
        "count": 3
    },
    "normal": {
        "query": {"is_ask": False,
                  "is_tell": False,
                  "is_show": False},
        "count": 24,
        "comment_seed_count": 1000000
    }
}

if pathlib.Path("data/posts.json").exists():
    with open("data/posts.json", "r") as fd:
        created_posts = json.load(fd)
else:
    created_posts = []


def train_from_query(query, cls):
    print("Generating Corpus")
    #corpus = io.StringIO()

    total = 0

    with Timer() as t:
        with tempfile.NamedTemporaryFile("w+b", delete=False) as fd:
            query = (t for t in query.yield_per(1000) if t[0])

            args = [iter(query)] * 100

            for data in itertools.zip_longest(*args, fillvalue=None):
                fd.writelines([(data[0] + "\n").encode("utf8") for data in data if data is not None])
                total += 1

            name = fd.name

        with open(name, encoding="utf8") as fd:
            corpus = fd.read()

        os.remove(name)

        print("Generated corpus ({total} entries) in {time:10f}, length: {len}".format(total=total * 100,
                                                                                       time=t.elapsed,
                                                                                       len=len(corpus)))

    with Timer() as t:
        sim = cls(corpus)

    print("Created simulation {0} in {time:10f} seconds".format(sim.__class__.__name__, time=t.elapsed))

    return sim


def make_comment(post_type):
    Session = sessionmaker(bind=engine)
    db = Session()

    dead_comments = db.query(Comment.text) \
        .filter(Comment.dead == True, Comment.text != None) \
        .order_by(func.random()).limit(30000)

    dead_comment_sim = train_from_query(dead_comments, CommentSim)

    comment_query = db.query(Comment.text).filter(Comment.dead == False)
    if post_type != "normal":
        comment_query = comment_query.filter(Comment.id.in_(
            db.query(func.unnest(Story.all_kids)).filter_by(**queries[post_type]["query"])
        ))
    comment_query = comment_query.order_by(func.random()).limit(60000)
    random_user_query = db.query(Comment.by).order_by(func.random())

    comment_sim = train_from_query(comment_query, CommentSim)

    user_names = (by[0] for by in random_user_query.limit(random.randint(0, 50)))
    comments = []

    for user_name in user_names:
        is_dead = random.randint(2, 100) < 5
        sim = comment_sim if not is_dead else dead_comment_sim

        comment_length, comment = random.randint(0, 200), ""

        while len(comment) < comment_length:
            if (comment_length - len(comment)) < 25:
                break
            elif (comment_length - len(comment)) < 50:
                comment += sim.make_short_sentence(50, tries=10000,
                                                   max_overlap_total=10,
                                                   max_overlap_ratio=0.5) + "\n"
            else:
                comment += sim.make_short_sentence(100,
                                                   tries=10000,
                                                   max_overlap_total=10,
                                                   max_overlap_ratio=0.5) + "\n"
        comment = comment.replace(".", ". ")
        comment_data = {"text": comment, "by": user_name, "dead": is_dead}
        comments.append(comment_data)

    return comments


def main():
    Session = sessionmaker(bind=engine)
    sesh = Session()
    print("Setting all_comments")
    result = sesh.execute(
    """
    CREATE OR REPLACE FUNCTION recurse_children(post_id INTEGER)
    RETURNS integer[] AS $$
    WITH RECURSIVE recursetree(id, parent_id) AS (
    SELECT id, parent_id FROM comments WHERE parent_id = post_id
    UNION
    SELECT t.id, t.parent_id
    FROM comments t
    JOIN recursetree rt ON rt.id = t.parent_id
    ) SELECT array(SELECT id FROM recursetree);
    $$ LANGUAGE SQL;""")

    #sesh.execute("UPDATE posts SET all_kids=recurse_children(id) WHERE is_ask=true OR is_tell=true OR is_show=true;")
    sesh.execute("COMMIT")
    sesh.execute("BEGIN")

    """sesh.query(Story) \
        .filter(or_(Story.is_ask == True, Story.is_tell == True, Story.is_show == True))\
        .filter(Story.all_kids == None)\
        .update({"all_kids": func.recurse_children(Story.id)}, synchronize_session=False)"""
    print("Done")


    for post_type, info in queries.items():
        query_args = info["query"]
        title_query = sesh.query(Story.title).filter_by(**query_args).order_by(func.random())

        if post_type == "normal":
            title_query = title_query.filter(Story.score > 4)

        our_posts = []

        print("Generating title for post type {type}".format(type=post_type))

        title_sim = train_from_query(title_query, SubmissionTitleSim)

        with Timer() as t:
            for i in range(info["count"]):
                chosen_title = title_sim.make_sentence(tries=10000,
                                                       max_overlap_total=10,
                                                       max_overlap_ratio=0.5)
                domain, user = sesh.query(Story.host, Story.by).filter_by(**query_args).order_by(func.random()).limit(
                    1).one()
                votes = random.randint(1, 250)

                print(chosen_title + " ({domain})".format(domain=domain))
                print("[{votes}] By {by}".format(votes=votes, by=user))
                print()
                our_posts.append({
                    "id": len(created_posts) + len(our_posts),
                    "title": chosen_title,
                    "host": domain,
                    "by": user,
                    "votes": votes,
                    "comments": [],
                    "type": post_type
                })

        del title_sim

        print("Chosen title in {time:6.4f}".format(time=t.elapsed))

        comments = [post_type] * len(our_posts)
        pool = multiprocessing.Pool(processes=len(comments) if len(comments) < 5 else 5)
        comment_data = pool.map(make_comment, comments)

        for i, comments in enumerate(comment_data):
            post = our_posts[i]
            print("Made {0} comments".format(len(comments)))
            last_indent = None

            while comments:
                comm = comments.pop()
                choice = random.randint(0, 10)
                if last_indent is None:
                    last_indent = 0
                elif choice < 1:
                    # Reset
                    last_indent = 0
                elif choice < 4:
                    # Stay where we are
                    pass
                elif choice < 9:
                    # Indent
                    last_indent += 1
                else:
                    if last_indent:
                        # Dedent
                        last_indent -= 1

                comm["indent"] = last_indent
                post["comments"].append(comm)

        created_posts.extend(our_posts)

        print("-" * 30)

    with open("data/posts.json", "w") as fd:
        json.dump(created_posts, fd)


if __name__ == "__main__":
    main()
