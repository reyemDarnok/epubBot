import json
import re
from typing import Generator

import markdown
import praw
from bs4 import BeautifulSoup

version = '0.3'


def create_reddit_instance() -> praw.reddit.Reddit:
    with open("config.json") as configfile:
        config = json.load(configfile)

    return praw.Reddit(
        client_id=config['client_id'],
        client_secret=config['client_secret'],
        username='epubBot',
        password=config['password'],
        user_agent=f'linux:de.reyem.epubBot:{version} (by /u/epubBot)'
    )


def get_trigger_comments(reddit: praw.Reddit) -> Generator[praw.reddit.Comment, None, None]:
    generator = reddit.inbox.unread()
    for comment in generator:
        if comment is praw.reddit.Comment:
            comment.mark_read()
            yield comment


def yield_submissions(reddit: praw.reddit.Reddit, submission: praw.reddit.Submission, next_pattern: str) \
        -> Generator[praw.reddit.Submission, None, None]:
    yield submission
    soup = BeautifulSoup(markdown.markdown(submission.selftext), features='lxml')
    next_link = soup.find('a', text=re.compile(re.escape(next_pattern), re.IGNORECASE))
    while next_link is not None:
        submission = reddit.submission(url=next_link.attrs['href'])
        yield submission
        soup = BeautifulSoup(markdown.markdown(submission.selftext), features='lxml')
        next_link = soup.find('a', text=re.compile(re.escape(next_pattern), re.IGNORECASE))
