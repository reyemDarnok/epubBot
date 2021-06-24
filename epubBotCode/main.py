#!/usr/bin/env python3
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


if __name__ == '__main__':
    main()
