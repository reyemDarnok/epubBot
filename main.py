#!/bin/env python3
import re
from typing import List, Generator

from ebooklib import epub
import praw
import json
import shlex
import markdown
from bs4 import BeautifulSoup
import argparse

version = '0.1'


def main():
    reddit = create_reddit_instance()
    triggers = get_trigger_comments(reddit)
    for comment in triggers:
        create_epub(comment, reddit)


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
    generator = reddit.inbox.mentions()
    for comment in generator:
        comment.mark_read()
        yield comment


def create_epub(comment: praw.reddit.Comment, reddit: praw.reddit.Reddit):
    # noinspection PyBroadException
    try:
        args = command_argparse(comment.body)
        submission = comment.submission
        chapters = tuple()
        submission_html = markdown.markdown(submission.selftext)
        book = epub.EpubBook()
        soup = BeautifulSoup(submission_html, features='lxml')
        first_link = soup.find('a', text=re.compile(re.escape(args.first), re.IGNORECASE))
        post_num = 1
        title = submission.title
        if first_link is not None:
            submission = reddit.submission(url=first_link.attrs['href'])
            submission_html = markdown.markdown(submission.selftext)
            soup = BeautifulSoup(submission_html, features='lxml')
        else:
            previous_link = soup.find('a', text=re.compile(re.escape(args.previous), re.IGNORECASE))
            while previous_link is not None:
                submission = reddit.submission(url=previous_link.attrs['href'])
                submission_html = markdown.markdown(submission.selftext)
                soup = BeautifulSoup(submission_html, features='lxml')
                soup.find('a', text=re.compile(re.escape(args.previous), re.IGNORECASE))

        set_metadata(book, submission)

        for submission in yield_submissions(reddit, submission, args.next):
            print(f'Getting post {post_num}')
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
        # add default NCX and Nav file
        design(book, chapters)
        # write to the file
        epub.write_epub(f'{title}.epub', book, {})
    except argparse.ArgumentError:
        comment.reply(create_arg_parser().format_help())
    except:
        comment.reply("Encountered unknown error while creating epub. Check your arguments")


def command_argparse(command: str) -> argparse.Namespace:
    parser = create_arg_parser()
    return parser.parse_args(shlex.split(command)[1:])


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


def create_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="A bot that creates epubs from reddit posts.")
    parser.add_argument('-n', '--next', type=str, default='Next',
                        help='The link text for the link to the next the chapter, if any. '
                             'Case insensitive and accepts partial matches. Defaults to "Next".')
    parser.add_argument('-p', '--previous', type=str, default='Previous',
                        help='The link text for the link to the previous chapter, if any. '
                             'Case insensitive and accepts partial matches. Defaults to "Previous".')
    parser.add_argument('-f', '--first', type=str, default='First',
                        help='The link text for the link to the first chapter, if any. '
                             'Case insensitive and accepts partial matches. Defaults to "First".')
    parser.add_argument('-c', '--chapter-break', type=str, default='-',
                        help='This sequence repeated three or more times signals a new chapter. Defaults to "-".')
    parser.add_argument('--no-intro', action="store_true",
                        help='The first chapter is not introduction, to be discarded.'
                             'Defaults to true.')
    parser.add_argument('--no-outro', action="store_true",
                        help='The last chapter of a post is not an outro, to be discarded entirely.'
                             'Defaults to true.')
    parser.add_argument('-m', '--max-chapters', type=int, default=None,
                        help='How many chapters are at most detected. Defaults to no limit')
    return parser


def design(book, chapters):
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    # define CSS style
    style = 'BODY {color: white;}'
    nav_css = epub.EpubItem(uid="style_nav", file_name="style/nav.css", media_type="text/css", content=style)
    # add CSS file
    book.add_item(nav_css)
    # basic spine
    spine = ['nav'] + list(chapters)
    book.spine = spine


def set_metadata(book, submission):
    book.set_identifier(submission.fullname)
    book.set_title(submission.title)
    book.set_language('en')
    book.add_author(submission.author.name, file_as=submission.author_fullname)


if __name__ == '__main__':
    main()
