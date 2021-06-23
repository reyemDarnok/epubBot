#!/usr/bin/env python3
import re

from ebooklib import epub
import praw
import markdown
from bs4 import BeautifulSoup

from epub_methods import design, set_metadata
from project_argparse import command_argparse, create_arg_parser
from reddit_interaction import create_reddit_instance, get_trigger_comments, yield_submissions

version = '0.1'


def main():
    reddit = create_reddit_instance()
    triggers = get_trigger_comments(reddit)
    for comment in triggers:
        create_epub(comment, reddit)


def create_epub(comment: praw.reddit.Comment, reddit: praw.reddit.Reddit):
    # noinspection PyBroadException
    try:
        args = command_argparse(comment.body)
    except:
        comment.reply(create_arg_parser().format_help())
        return

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
    else:
        previous_link = soup.find('a', text=re.compile(re.escape(args.previous), re.IGNORECASE))
        while previous_link is not None:
            submission = reddit.submission(url=previous_link.attrs['href'])
            submission_html = markdown.markdown(submission.selftext)
            soup = BeautifulSoup(submission_html, features='lxml')
            soup.find('a', text=re.compile(re.escape(args.previous), re.IGNORECASE))

    set_metadata(book, submission, args)

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

    design(book, chapters)
    # noinspection PyBroadException
    try:
        epub.write_epub(f'{title}.epub', book, {})
    except:
        comment.reply('Failed to create epub. Maybe one of your parameters is set wrong? Common mistakes are empty '
                      'chapters')


if __name__ == '__main__':
    main()
