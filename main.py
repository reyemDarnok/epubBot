#!/bin/env python3
import re
from typing import List

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


def get_trigger_comments(reddit: praw.Reddit) -> List[praw.reddit.Comment]:
    return [reddit.comment(url='https://www.reddit.com/r/HFY/comments/f6iwyk/of_men_and_dragons_chapter_1/fi53y86'
                               '?utm_source=share&utm_medium=web2x&context=3')]


def create_epub(comment: praw.reddit.Comment, reddit: praw.reddit.Reddit):
    try:
        args = command_argparse('')  # comment.body
        submission = comment.submission
        chapters = tuple()
        submission_html = markdown.markdown(submission.selftext)
        book = epub.EpubBook()
        soup = BeautifulSoup(submission_html, features='lxml')
        first_link = soup.find('a', text=re.compile(re.escape(args.first), re.IGNORECASE))
        chapter_num = 1
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

        while submission is not None:
            print(f'Getting Chapter {chapter_num}')
            chapter = epub.EpubHtml(title=submission.title, file_name=f'{submission.title}.xhtml')
            chapter_num += 1
            chapter.content = submission_html
            book.add_item(chapter)
            chapters += tuple([chapter])
            next_link = soup.find('a', text=re.compile(re.escape(args.next), re.IGNORECASE))
            if next_link is not None:
                submission = reddit.submission(url=next_link.attrs['href'])
                submission_html = markdown.markdown(submission.selftext)
                soup = BeautifulSoup(submission_html, features='lxml')
            else:
                submission = None

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
        print(create_arg_parser().print_help())


def command_argparse(command: str) -> argparse.Namespace:
    parser = create_arg_parser()
    return parser.parse_args(shlex.split(command)[1:])


def create_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="A bot that creates epubs from reddit posts.")
    parser.add_argument('-n', '--next', type=str, default='Next',
                        help='The link text for the link to the next the chapter, if any. '
                             'Defaults to "Next".')
    parser.add_argument('-p', '--previous', type=str, default='Previous',
                        help='The link text for the link to the previous chapter, if any. '
                             'Defaults to "Previous".')
    parser.add_argument('-f', '--first', type=str, default='First',
                        help='The link text for the link to the first chapter, if any. '
                             'Defaults to "First".')
    parser.add_argument('-c', '--chapter-break', type=str, default='-',
                        help='This sequence repeated three or more times signals a new chapter. Defaults to "-".')
    parser.add_argument('--has-intro', type=bool, default=True,
                        help='Whether to consider the first chapter of a post to be introduction.'
                             'Only the first chapters introduction will be included in the epub. Defaults to true.')
    parser.add_argument('--has-outro', type=bool, default=True,
                        help='Whether to consider the last chapter of a post to be an outro, to be discarded entirely.'
                             'Defaults to true.')
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
