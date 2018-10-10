#!/usr/bin/env python3

if __name__ == "__main__":
    import argparse, json, os.path
    from syrocr.getlines import getlines, drawboxes

    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose",
        help="increase output verbosity",
        action="store_true")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--getlines",
        metavar='source_image',
        help="""Get lines from source_image,
                write to json file, and save image with drawboxes""")
    group.add_argument("--drawboxes",
        nargs=2,
        metavar=('source_image', 'json_file'),
        help="Draw boxes from lines in json_file on source_image")

    args = parser.parse_args()

    if args.getlines:
        source_image = args.getlines
        basename = os.path.basename(os.path.splitext(source_image)[0])
        lines = getlines(source_image, dpi=(300,300), verbose=False)
        im_lines = drawboxes(source_image, lines)
        im_lines.save(basename + '_lines.png', format="PNG")
        with open(basename + '_lines.json', 'w') as f:
            json.dump(lines, f, indent=2)
    elif args.drawboxes:
        source_image, json_file = args.drawboxes
        basename = os.path.basename(os.path.splitext(source_image)[0])
        with open(json_file) as f:
            lines = json.load(f)
        im_lines = drawboxes(source_image, lines)
        im_lines.save(basename + '_lines.png', format="PNG")
