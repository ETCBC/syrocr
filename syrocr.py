#!/usr/bin/env python3

from syrocr.getlines import getlines, drawboxes
import os.path, json

def usage():
    print("""Usage:
python3 syrocr.py getlines filename""")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose",
        help="increase output verbosity",
        action="store_true")
    parser.add_argument("--getlines",
        metavar='source_image',
        required=True,
        help="""Get lines from source_image,
                write to json file, and save image with drawboxes""")

    args = parser.parse_args()

    if args.getlines:
        source_file = args.getlines
        basename = os.path.basename(os.path.splitext(source_file)[0])
        lines = getlines(source_file, dpi=(300,300), verbose=False)
        im_lines = drawboxes(source_file, lines)
        im_lines.save(basename + '_lines.png', format="PNG")
        with open(basename + '_lines.json', 'w') as f:
            json.dump(lines, f, indent=2)
