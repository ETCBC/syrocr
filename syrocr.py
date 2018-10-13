#!/usr/bin/env python3

import argparse, json, sys, os.path
from syrocr.getlines import getlines, drawboxes

def command_getlines(args):
    source_image = args.source_image
    basename = os.path.basename(os.path.splitext(source_image)[0])
    lines = getlines(source_image, dpi=(300,300), verbose=args.verbose)
    im_lines = drawboxes(source_image, lines)
    im_lines.save(basename + '_lines.png', format="PNG")
    with open(basename + '_lines.json', 'w') as f:
        json.dump(lines, f, indent=2)

def command_drawboxes(args):
    source_image = args.source_image
    json_file = args.json_file
    basename = os.path.basename(os.path.splitext(source_image)[0])
    with open(json_file) as f:
        lines = json.load(f)
    im_lines = drawboxes(source_image, lines)
    im_lines.save(basename + '_lines.png', format="PNG")

if __name__ == "__main__":
    # initialize main argument parser
    parser = argparse.ArgumentParser(
        epilog='For help on subcommands, '
               'see: %(prog)s <subcommand> -h')

    # initialize subparsers
    subparsers = parser.add_subparsers(
        title='subcommands',
        help='subcommand description:',
        dest='command',
        metavar='<subcommand>')

    # initialize subparser p_getlines
    p_getlines = subparsers.add_parser(
        'getlines',
        help='Get lines from source image')
    p_getlines.add_argument(
        '-v', '--verbose',
        help='increase output verbosity',
        action='store_true')
    p_getlines.add_argument(
        'source_image',
        help='Filename of source image')
    p_getlines.set_defaults(func=command_getlines)

    # initialize subparser p_drawboxes
    p_drawboxes = subparsers.add_parser(
        'drawboxes',
        help='Draw boxes around lines on source image')
    p_drawboxes.add_argument(
        'source_image',
        help='Filename of source image')
    p_drawboxes.add_argument(
        'json_file',
        help='Filename of json file')
    p_drawboxes.set_defaults(func=command_drawboxes)

    # parse arguments
    args = parser.parse_args()

    # execute default function set in parser.set_defaults()
    if args.command is not None:
        args.func(args)
    # or print help text if no command was given
    else:
        parser.print_help()
