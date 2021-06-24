#!/usr/bin/env python3
import argparse
import re
import urllib
import logging

from aws_api import upload_to_s3
from project_argparse import command_argparse, create_arg_parser
from reddit_api import create_reddit_instance, get_trigger_comments, yield_submissions
from epub_metadata import design, set_metadata

from ebooklib import epub
import praw
import markdown
from bs4 import BeautifulSoup


def main(event=None, context=None):
    logging.getLogger().setLevel(logging.INFO)
    reddit_instance = create_reddit_instance()
    triggers = get_trigger_comments(reddit_instance)
    for comment in triggers:
        create_epub(comment, reddit_instance)


def create_epub(comment: praw.reddit.Comment, reddit_instance: praw.reddit.Reddit):
    logger = logging.getLogger('create_epub')
    # noinspection PyBroadException
    try:
        args = command_argparse(comment.body)
    except ValueError:
        return
    except SystemExit:  # from argparse fail
        comment.reply(create_arg_parser().format_help())
        logger.info(f'Invalid command {comment.body}')
        return

    chapters = tuple()
    book = epub.EpubBook()

    submission = find_first_submission(args, logger, reddit_instance, comment.submission)
    post_num = 1
    title: str = submission.title

    set_metadata(book, submission, args)

    for submission in yield_submissions(reddit_instance, submission, args.next):
        logging.debug(f'Getting post {post_num}')
        post_num += 1
        if args.max_chapters is not None and post_num > args.max_chapters:
            break
        chapter_texts = split_posts_into_chapters(args, submission)
        chapter_num = 1
        single_chapter_post = len(chapter_texts) == 0
        for text in chapter_texts:
            chapter = create_chapter(book, chapter_num, single_chapter_post, submission.title, text)
            chapters += tuple([chapter])
            chapter_num += 1

    book.toc = (epub.Link('toc.xhtml', 'Totality', 'total'),
                (epub.Section('Book'),
                 chapters)
                )

    design(book, chapters)
    publish_epub(book, comment, title)


def publish_epub(book: epub.EpubBook, comment: praw.reddit.Comment, title: str):
    try:
        logging.info(f'Creating epub for {title}')
        epub.write_epub(f'/tmp/{title}.epub', book, {})
        upload_to_s3(f'{title}.epub')
        comment.reply(f'https://reyem-epub-bot-output.s3.us-east-2.amazonaws.com/'
                      f'{urllib.parse.quote(title).replace("%20", "+")}.epub')
    except Exception as ex:
        logging.info(f'Failed to create to epub. Informing requesting user. Exception was {str(ex)}')
        comment.reply('Failed to create epub. Maybe one of your parameters is set wrong? Common mistakes are empty '
                      'chapters')


def split_posts_into_chapters(args: argparse.Namespace, submission: praw.reddit.Submission):
    chapter_texts = submission.selftext.split(args.chapter_break * 3)
    chapter_texts = [x for x in chapter_texts if x != '']
    if not args.no_intro:
        chapter_texts = chapter_texts[1:]
    if not args.no_outro:
        chapter_texts = chapter_texts[:-1]
    return chapter_texts


def create_chapter(book: epub.EpubBook, chapter_num: int, single_chapter_post: bool, post_title: str, text: str)\
        -> epub.EpubHtml:
    chapter_title = post_title if single_chapter_post else f'{post_title} {chapter_num}'
    text = f'#{chapter_title}\n' + text
    submission_html = markdown.markdown(text)
    chapter = epub.EpubHtml(title=chapter_title, file_name=f'{chapter_title}.xhtml')
    chapter.content = submission_html
    book.add_item(chapter)
    return chapter


def find_first_submission(args: argparse.Namespace, logger: logging.Logger, reddit_instance: praw.reddit.Reddit,
                          submission: praw.reddit.Submission) -> praw.reddit.Submission:
    submission_html = markdown.markdown(submission.selftext)
    soup = BeautifulSoup(submission_html, features='lxml')
    first_link = soup.find('a', text=re.compile(re.escape(args.first), re.IGNORECASE))
    if first_link is not None:
        submission = reddit_instance.submission(url=first_link.attrs['href'])
        logger.info(f'Found first post in chain: {submission.title}')
    else:
        previous_link = soup.find('a', text=re.compile(re.escape(args.previous), re.IGNORECASE))
        while previous_link is not None:
            submission = reddit_instance.submission(url=previous_link.attrs['href'])
            submission_html = markdown.markdown(submission.selftext)
            soup = BeautifulSoup(submission_html, features='lxml')
            soup.find('a', text=re.compile(re.escape(args.previous), re.IGNORECASE))
        logger.info(f'Walked previous links to first in chain: {submission.title}')
    return submission


if __name__ == '__main__':
    main()
