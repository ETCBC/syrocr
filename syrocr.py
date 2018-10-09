#!/usr/bin/env python3

def usage():
    print("""Usage:
python3 syrocr.py getlines filename""")

if __name__ == "__main__":
    # TODO This should be done with argparse
    import sys
    args = sys.argv[1:]
    if len(args) < 2:
        usage()
        sys.exit(2)
    if args[0] == "getlines":
        # try:
        from syrocr.getlines import getlines, drawboxes
        import os.path, json
        filepath = args[1]
        basename = os.path.basename(os.path.splitext(filepath)[0])
        lines = getlines(filepath, dpi=(300,300), verbose=False)
        im_lines = drawboxes(filepath, lines)
        im_lines.save(basename + '_lines.png', format="PNG")
        with open(basename + '_lines.json', 'w') as f:
            json.dump(lines, f, indent=2)
