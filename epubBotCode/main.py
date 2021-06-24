#!/usr/bin/env python3
import argparse
import json
import os
import re
import shlex
import sys
import urllib
from typing import Dict, Any, Tuple, List, Union, Generator
import logging
import boto3

version = '1.0'

from ebooklib import epub
import praw
import markdown
from bs4 import BeautifulSoup
from praw import reddit
from smart_open import smart_open


def main():
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
    except:
        comment.reply(create_arg_parser().format_help())
        logger.info(f'Invalid command {comment.body}')
        return

    submission = comment.submission
    chapters = tuple()
    submission_html = markdown.markdown(submission.selftext)
    book = epub.EpubBook()
    soup = BeautifulSoup(submission_html, features='lxml')
    first_link = soup.find('a', text=re.compile(re.escape(args.first), re.IGNORECASE))
    post_num = 1
    title: str = submission.title
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

    set_metadata(book, submission, args)

    for submission in yield_submissions(reddit_instance, submission, args.next):
        logging.debug(f'Getting post {post_num}')
        post_num += 1
        if args.max_chapters is not None and post_num > args.max_chapters:
            break
        chapter_texts = submission.selftext.split(args.chapter_break * 3)
        chapter_texts = [x for x in chapter_texts if x != '']
        if not args.no_intro:
            chapter_texts = chapter_texts[1:]
        if not args.no_outro:
            chapter_texts = chapter_texts[:-1]
        chapter_num = 1
        for text in chapter_texts:
            chapter_title = submission.title if len(chapter_texts) == 1 else f'{submission.title} {chapter_num}'
            chapter_num += 1
            text = f'#{chapter_title}\n' + text
            submission_html = markdown.markdown(text)
            chapter = epub.EpubHtml(title=chapter_title, file_name=f'{chapter_title}.xhtml')
            chapter.content = submission_html
            book.add_item(chapter)
            chapters += tuple([chapter])

    # define Table Of Contents
    book.toc = (epub.Link('toc.xhtml', 'Totality', 'total'),
                (epub.Section('Book'),
                 chapters)
                )

    design(book, chapters)
    # noinspection PyBroadException
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


def upload_to_s3(filename: str):
    logger = logging.getLogger('aws')
    logger.info(f'Uploading {filename} to aws bucket')
    with smart_open(f's3://reyem-epub-bot-output/{filename}', 'wb') as fout:
        with smart_open(f'/tmp/{filename}', 'rb') as fin:
            for line in fin:
                fout.write(line)
    logger.debug(f'Finished uploading {filename} to aws bucket')


def get_config_from_s3() -> Dict[Any, Any]:
    logger = logging.getLogger('aws')
    logger.debug('Read config from s3 bucket')
    text = ''
    with smart_open('s3://reyem-epub-bot-config/config.json', 'rb') as s3_file:
        for line in s3_file:
            text += line.decode('utf8')
    logger.debug('Finished reading config from s3 bucket')
    return json.loads(text)


def design(book: epub.EpubBook, chapters: Tuple[epub.EpubHtml]):
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    # define CSS style
    style = 'BODY {color: white;}'
    nav_css = epub.EpubItem(uid="style_nav", file_name="style/nav.css", media_type="text/css", content=style)
    # add CSS file
    book.add_item(nav_css)
    # basic spine
    spine: List[Union[str, epub.EpubHtml]] = ['nav']
    spine += list(chapters)
    book.spine = spine


def set_metadata(book: epub.EpubBook, submission: reddit.Submission, args: argparse.Namespace):
    book.set_identifier(submission.fullname)
    book.set_title(submission.title if args.title is None else args.title)
    book.set_language(args.language)
    book.add_author(submission.author.name if args.author is None else args.author,
                    file_as=submission.author_fullname if args.file_as is None else args.file_as)


def command_argparse(command: str) -> argparse.Namespace:
    logger = logging.getLogger('argparse')
    logger.debug(f'Parsing command {command}')
    parser = create_arg_parser()
    argv = shlex.split(command)
    if argv[0] != 'u/epubBot':
        logger.info('Found an errant mention')
        raise ValueError('Not a invocation')
    return parser.parse_args(argv[1:])


def create_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="A bot that creates epubs from reddit posts.",
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-n', '--next', type=str, default='Next',
                        help='The link text for the link to the next the chapter, if any. '
                             'Case insensitive and accepts partial matches. Defaults to "Next".\n\n')
    parser.add_argument('-p', '--previous', type=str, default='Previous',
                        help='The link text for the link to the previous chapter, if any. '
                             'Case insensitive and accepts partial matches. Defaults to "Previous".\n\n')
    parser.add_argument('-f', '--first', type=str, default='First',
                        help='The link text for the link to the first chapter, if any. '
                             'Case insensitive and accepts partial matches. Defaults to "First".\n\n')
    parser.add_argument('-c', '--chapter-break', type=str, default='-',
                        help='This sequence repeated three or more times signals a new chapter. Defaults to "-".\n\n')
    parser.add_argument('--no-intro', action="store_true",
                        help='The first chapter is not introduction, to be discarded.'
                             'Defaults to true.\n\n')
    parser.add_argument('--no-outro', action="store_true",
                        help='The last chapter of a post is not an outro, to be discarded entirely.'
                             'Defaults to true.\n\n')
    parser.add_argument('-m', '--max-chapters', type=int, default=None,
                        help='How many chapters are at most detected. Defaults to no limit.\n\n')
    parser.add_argument('-t', '--title', type=str, default=None,
                        help='The books title. Defaults to the title of the post.\n\n')
    parser.add_argument('-l', '--language', type=str, default='en',
                        help='The books language (as a tag). Defaults to "en".\n\n')
    parser.add_argument('-a', '--author', type=str, default=None,
                        help='The books author. Defaults to the posters username.\n\n')
    parser.add_argument('--file-as', type=str, default=None,
                        help='The name of the author for filing purposes.\n\n')
    return parser


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


def lambda_handler(event, context):
    main()


if __name__ == '__main__':
    main()
