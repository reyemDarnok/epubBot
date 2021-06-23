import argparse
import shlex


def command_argparse(command: str) -> argparse.Namespace:
    parser = create_arg_parser()
    return parser.parse_args(shlex.split(command)[1:])


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