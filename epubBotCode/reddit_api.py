import logging
import re
from typing import Generator

import markdown
import praw
from bs4 import BeautifulSoup

from aws_api import get_config_from_s3


def create_reddit_instance() -> praw.reddit.Reddit:
    logger = logging.getLogger('reddit')
    config = get_config_from_s3()

    reddit_instance = praw.Reddit(
        client_id=config['client_id'],
        client_secret=config['client_secret'],
        username='epubBot',
        password=config['password'],
        user_agent=f'linux:de.reyem.epubBot:{version} (by /u/epubBot)'
    )
    logger.info('Authorised to reddit')
    return reddit_instance


def get_trigger_comments(reddit_instance: praw.Reddit) -> Generator[praw.reddit.Comment, None, None]:
    logger = logging.getLogger('reddit')
    generator = reddit_instance.inbox.mentions()
    for comment in generator:
        logger.debug(f'Found comment {comment.fullname}')
        if comment.new:
            logger.info(f'Found trigger comment {comment.fullname}')
            comment.mark_read()
            yield comment
        else:
            logger.debug(f'Discarding comment {comment.fullname} as read')


def yield_submissions(reddit_instance: praw.reddit.Reddit, submission: praw.reddit.Submission, next_pattern: str) \
        -> Generator[praw.reddit.Submission, None, None]:
    logger = logging.getLogger('reddit')
    logger.info(f'Returning submission {submission.title}')
    yield submission
    soup = BeautifulSoup(markdown.markdown(submission.selftext), features='lxml')
    next_link = soup.find('a', text=re.compile(re.escape(next_pattern), re.IGNORECASE))
    while next_link is not None:
        submission = reddit_instance.submission(url=next_link.attrs['href'])
        logger.info(f'Returning submission {submission.title}')
        yield submission
        soup = BeautifulSoup(markdown.markdown(submission.selftext), features='lxml')
        next_link = soup.find('a', text=re.compile(re.escape(next_pattern), re.IGNORECASE))


version = '1.0'