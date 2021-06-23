import argparse
from typing import Tuple

from ebooklib import epub
from praw import reddit


def design(book: epub.EpubBook, chapters: Tuple[epub.EpubHtml]):
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


def set_metadata(book: epub.EpubBook, submission: reddit.Submission, args: argparse.Namespace):
    book.set_identifier(submission.fullname)
    book.set_title(submission.title if args.title is None else args.title)
    book.set_language(args.language)
    book.add_author(submission.author.name if args.author is None else args.author,
                    file_as=submission.author_fullname if args.file_as is None else args.file_as)
