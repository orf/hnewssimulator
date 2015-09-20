from contexttimer import Timer
from db import Base, Story, Comment
from sqlalchemy import create_engine
import markovify
import io
from sqlalchemy.sql import func
import random
from sqlalchemy.orm import sessionmaker
import json
import pathlib


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
        # split everything up by newlines, prepare them, and join back together
        return text.splitlines()


engine = create_engine("postgresql://hnews:hnews@localhost/hnews")
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
sesh = Session()

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

sesh.execute("UPDATE posts SET all_kids=recurse_children(id) WHERE ARRAY_LENGTH(all_kids, 1) IS NULL OR ARRAY_LENGTH(black_list, 1) < 1")
print("Done")

if pathlib.Path("data/posts.json").exists():
    with open("data/posts.json", "r") as fd:
        created_posts = json.load(fd)
else:
    created_posts = []


def train_from_query(query, cls):
    print("Generating Corpus")
    corpus = io.StringIO()

    total = 0
    for data in (t for t in query.yield_per(10000) if t[0]):
        corpus.write(data[0] + "\n")
        total += 1

    print("Generated corpus ({total} entries), length: {len}".format(total=total, len=len(corpus.getvalue())))

    with Timer() as t:
        sim = cls(corpus.getvalue())

    print("Created simulation in {time:10f} seconds".format(time=t.elapsed))

    return sim


dead_comments = sesh.query(Comment.text) \
    .filter(Comment.dead == True, Comment.text != None) \
    .order_by(func.random()).limit(30000)

dead_comment_sim = train_from_query(dead_comments, CommentSim)


def main():
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

        comment_query = sesh.query(Comment.text)
        if post_type != "normal":
            comment_query = comment_query.filter(Comment.id.in_(
                sesh.query(func.unnest(Story.all_kids)).filter_by(**query_args)
            ))
        comment_query = comment_query.order_by(func.random()).limit(40000)

        random_user_query = sesh.query(Comment.by).order_by(func.random())

        for new_post in our_posts:
            comment_sim = train_from_query(comment_query, CommentSim)

            user_names = (by[0] for by in random_user_query.limit(random.randint(0, 150)))
            comments = []

            for user_name in user_names:
                is_dead = random.randint(2, 100) < 5
                sim = comment_sim if not is_dead else dead_comment_sim

                comment_length, comment = random.randint(0, 500), ""

                while len(comment) < comment_length:
                    comment += sim.make_sentence(tries=10000,
                                                 max_overlap_total=10,
                                                 max_overlap_ratio=0.5)

                comment_data = {"text": comment, "by": user_name, "dead": is_dead}
                comments.append(comment_data)
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

                new_post["comments"].append(comm)

        created_posts.extend(our_posts)

        print("-" * 30)

    with open("data/posts.json", "w") as fd:
        json.dump(created_posts, fd)


if __name__ == "__main__":
    main()
