#!/usr/bin/env python3

import argparse, json, sys, os.path
from syrocr.getlines import getlines, drawboxes
from syrocr.getchars import scanpage
from syrocr.images import AvgIm

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

def command_getchars(args):
    basename = os.path.basename(os.path.splitext(args.source_image)[0])

    with open(args.json_lines_file, 'r') as f:
        lines = json.load(f)

    with open(args.json_tables_file, 'r') as f:
        tables = json.load(f)
    for textsize in tables:
        for entry in tables[textsize]:
            entry['avgim'] = AvgIm(
                entry['avgim']['base64_str'],
                entry['avgim']['baseline'],
                entry['avgim']['width'],
                entry['avgim']['height']
                )
    textlines, tables = scanpage(args.source_image, lines, tables, verbose=args.verbose)

    with open(basename + '_textlines.json', 'w') as f:
        json.dump(textlines, f, indent=2)
    # TODO try converting avgim in json.dump with default serializer: https://stackoverflow.com/a/41200652
    for textsize in tables:
        for entry in tables[textsize]:
            entry['avgim'] = entry['avgim'].export()
    with open(args.json_tables_file, 'w') as f:
        json.dump(tables, f)

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

    # initialize subparser p_drawboxes
    p_getchars = subparsers.add_parser(
        'getchars',
        help='Recognize individual characters')
    p_getchars.add_argument(
        '-v', '--verbose',
        help='increase output verbosity',
        action='store_true')
    p_getchars.add_argument(
        'source_image',
        help='Filename of source image')
    p_getchars.add_argument(
        'json_lines_file',
        help='Filename of json lines file')
    p_getchars.add_argument(
        'json_tables_file',
        help='Filename of json tables file')
    p_getchars.set_defaults(func=command_getchars)

    # parse arguments
    args = parser.parse_args()

    # execute default function set in parser.set_defaults()
    if args.command is not None:
        args.func(args)
    # or print help text if no command was given
    else:
        parser.print_help()
