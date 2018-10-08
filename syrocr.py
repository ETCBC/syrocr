def usage():
    print("""Usage:
syrocr.py getlines filename""")

if __name__ == "__main__":
    # TODO This should be done with argparse
    import sys
    args = sys.argv[1:]
    if len(args) < 2:
        usage()
        sys.exit(2)
    if args[0] == "getlines":
        # try:
        from syrocr.getlines import getlines
        for line in getlines(args[1], dpi=(300,300), verbose=False):
            print(line)
