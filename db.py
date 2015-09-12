from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, Text, String, DateTime, Boolean
from sqlalchemy.dialects.postgresql import ARRAY

Base = declarative_base()


class Story(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True)
    title = Column(String)
    by = Column(String)
    time = Column(DateTime)
    text = Column(Text, nullable=True)
    url = Column(String, nullable=True)
    score = Column(Integer)

    kids = Column(ARRAY(Integer, dimensions=1))
    dead = Column(Boolean)
    descendants = Column(Integer)

    is_ask = Column(Boolean)
    is_show = Column(Boolean)


class Comment(Base):
    __tablename__ = "comments"
    id = Column(Integer, primary_key=True)

    by = Column(String)
    time = Column(DateTime)
    text = Column(Text)
    kids = Column(ARRAY(Integer, dimensions=1))
    parent_id = Column(Integer, index=True)
    dead = Column(Boolean)

