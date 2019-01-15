import os
import json


META = ('+', '|', '-', '{', '}')
DIACRITICS = ('#,', '#"', '#!', '#_', '^,', '^!', '^_', '"', '#', '^', '~')
INTERPUNCTION = ('#.', '#:', '#\\', # below the baseline
    '=.', '=/', '=:', '=\\', # on the baseline
    '^.', '^"', '^:', '^\\', # above the baseline
    '*', '.', '@', '_', 'o') # pericope markers
LETTERS = ("'", 'b', 'g', 'd', 'h', 'w', 'z', 'H', 'T', 'y', 'k',
    'l', 'm', 'n', 's', '`', 'p', 'S', 'q', 'r', '$', 't')
BRACKETS = '<>()'


class Char:
    def __init__(self, tr, connections, script, box, dist):
        self.tr = tr
        self.connections = connections
        self.script = script
        self.box = box
        self.dist = dist


def verses(*args, inscr=True, spaces_file=None, **kwargs):
    """Get text verse tuples"""
    chars = get_text(*args, **kwargs)
    if spaces_file is not None:
        chars = fix_spaces(chars, spaces_file=spaces_file)
    return chars_to_verses2(chars, inscr=inscr)

def chars_to_verses2(chars, inscr, newlines=True):
    line = []
    for char in chars:
        if newlines and char.tr == '\n':
            yield ('', ' '.join(''.join(line).split()))
            line = []
        else:
            line.append(char.tr)
    yield ('', ' '.join(''.join(line).split()))


def chars_to_verses(chars, inscr=True):
    """Convert sequence of characters to (tag, text) verse tuples"""
    def join_verse(tag, text):
        tag = ''.join(tag)
        if ' ' in tag:
            tag = tag[0] + ' '.join(reversed(tag[1:-1].split())) + tag[-1]
        text = ' '.join(''.join(text).split())
        return (tag, text)

    tag_start = False
    tag = []
    text = []
    inscr_start = False
    inscr_txt = []
    for char in chars:
        if char.tr == '(':
            if tag or text:
                yield join_verse(tag, text)
            tag.clear()
            text.clear()
            tag_start = True
            tag.append(char.tr)
        elif tag_start and char.tr == ')':
            tag.append(char.tr)
            tag_start = False
        elif tag_start:
            tag.append(char.tr)
        elif char.tr == '<':
            inscr_start = True
            inscr_txt.append(char.tr)
        elif inscr_start and char.tr == '>':
            inscr_txt.append(char.tr)
            inscr_start = False
        elif inscr_start:
            inscr_txt.append(char.tr)
        else:
            if char.tr != ' ' and inscr_txt:
                if inscr:
                    text.extend(inscr_txt)
                inscr_txt.clear()
            text.append(char.tr)
    if inscr_txt:
        if inscr:
            text.extend(inscr_txt)
        inscr_txt.clear()
    yield join_verse(tag, text)

def get_text(json_textlines_dir, tables_filename,
    json_texline_ext='_textlines.json',
    combinations=None, corrections=None,
    meta=False, interp=True, diacr=True):
    """Get text from json textlines files and tables

    Yields:
        pass
    """
    if combinations is None:
        combinations = []
    if corrections is None:
        corrections = []

    with open(tables_filename, 'r') as f:
        tables = json.load(f)
    # TODO for now we only look at line type 'text',
    # there section 'main', which has always textsize 'normal'.
    # This should be properly set in an argument.
    # table = tables['normal']
    table = tables['small']

    with os.scandir(json_textlines_dir) as sd:
        filenames = sorted(f.path for f in sd
            if f.is_file() and f.name.endswith(json_texline_ext))
    for filename in filenames:
        basename = os.path.basename(filename)[:-len(json_texline_ext)]
        with open(filename, 'r') as f:
            textlines = json.load(f)
        file_corrections = [c for c in corrections if c[0][0] == basename]

        for textline in textlines:
            # TODO for now we only look at line type 'text',
            # there section 'main'. This should be set in an argument.
            # if textline['type'] != 'text':
            if textline['type'] != 'column':
                continue

            line_corrections = [c for c in file_corrections
                                if c[0][1] == textline['num']]

            chars = get_textline(table, textline['main'], basename,
                textline['num'], combinations, line_corrections)

            # SOME FIXES TODO MUST BE FIXED IN OTHER WAYS
            chars = replace_dagger(chars) # emergency fix, see docstring
            chars = replace_brackets(chars) # another emergency fix
            chars = split_brackets(chars)
            chars = flip_yudh_sade(chars)

            # spaces must be added before reversing the line,
            # since afterward the order of the characters is
            # changed, and distance cannot be reliably established
            chars = add_spaces(chars)
            chars = reverse_line(chars)

            # apply some optional filters
            if not meta:
                chars = remove_meta(chars)
            if not interp:
                chars = remove_interpunction(chars)
            if not diacr:
                chars = remove_diacritics(chars)

            for char in chars:
                yield char

def get_textline(table, entries, basename, line_num,
             combinations=None, corrections=None):
    """Get actual characters from textlines.json data.

    Look up the recognized character id's in the character table,
    make some corrections such as combining broken characters and
    certain other combined characters, and replace certain manually
    corrected individual characters.

    Arguments:
        table: the list of dictionaries containing the character
            tables for the specific type of line.
        entries: a list of 4-tuples with the character information,
            namely: c_id, connections, keyoverride, box.
            c_id: int, position of character in character table.
            connections: 2-tuple with boolean values indicating
                whether the character is connected with a connecting
                line to the left and right respectively.
            keyoverride: replacement transcription this specific
                character. Not used now, replaced by 'corrections'.
            box: 4-tuple of int's, with (x1, y1, x2, y2) geometry values.
        basename: str, basename of page/image, to check location of
            'corrections'.
        line_num: int, number of line on page, to check location of
            'corrections'.
        combinations: list of 2-tuples, with first element a tuple,
            containing a combination of transcription strings,
            and the second element the replacement.
            E.g.: The recognized transcriptions 'n^', '"?'
            (meaning "nun" with one dot above, and an isolated dot,
            which is probably part of a broken seyame, as it is here)
            must be replaced by a "nun" with seyame, 'n"'.
            The combination tuple: (('n^', '"?'), 'n"')
            The first element can have any number of members.
        corrections: list of 2-tuples, with first element a tuple,
            containing the location of the symbol to be corrected,
            and the second the replacement string.
            The location is a tuple containing the basename of the
            page/image, line number, character position, and c_id.

    Yields:
        4-tuple: (tr, connections, script, box)
            tr: str, transcription of recognized character
            connections: 2-tuple with boolean values indicating
                whether the character is connected with a connecting
                line to the left and right respectively.
            script: str, identifier of character script
                ('' for syriac, 'r' for roman, 'c' for cursive, etc)
            box: 4-tuple of int's, with (x1, y1, x2, y2) geometry values.

    Todo:
        * Make proper class for entries, with attributes:
            c_id, connections, keyoverride, box
        * do something with dist (or not?)

    """
    if combinations is None:
        combinations = []
    if corrections is None:
        corrections = []

    m_stack = [] # stack of potentially matching characters
    l_stack = [] # loop stack

    for i, entry in enumerate(entries):
        c_id, connections, keyoverride, box = entry
        tr = table[c_id]['key']['tr'] if keyoverride is None else keyoverride
        dist = table[c_id]['key']['dist']
        script = table[c_id]['key']['script']

        # check if current char is in corrections list
        for correction in [c for c in corrections
                            if c[0][0] == basename
                            and c[0][1] == line_num
                            and c[0][2] == i
                            and c[0][3] == c_id]:
            tr = correction[1]

        l_stack.append(Char(tr, connections, script, box, dist))

        while l_stack:
            char = l_stack.pop(0)

            # discard entries with empty translation:
            if char.tr == '':
                continue
            elif m_stack:
                # if there are items on the m_stack, check combinations
                if (len(m_stack) == 1
                        and m_stack[0].tr.endswith('+')
                        and char.tr.startswith('+')
                        and m_stack[0].tr[:-1] == char.tr[1:]):
                    # combine split characters such as 'T+', '+T'
                    char.tr = char.tr[1:]
                    char.connections = [m_stack[0].connections[0], char.connections[1]]
                    char.box = combineboxes([m_stack[0].box, char.box])
                    yield char
                    m_stack.clear()
                    continue
                else:
                    pos = 0
                    # copy combinations, to select matching combinations
                    matches = combinations
                    while len(m_stack) > pos:
                        matches = [c for c in matches
                                   if (len(c[0]) > pos
                                   and c[0][pos] == m_stack[pos].tr)]
                        pos += 1
                    if not matches:
                        raise ValueError('Stack contains unmatched char.')
                    elif [c for c in matches
                            if (len(c[0]) > pos + 1
                            and c[0][pos]) == char.tr]:
                        # there are matching combinations with more members than current,
                        # so add current char to m_stack:
                        m_stack.append(char)
                        continue
                    else:
                        matches = [c for c in matches
                                    if (len(c[0]) > pos
                                    and c[0][pos]) == char.tr]
                        if not matches:
                            # first, put current char back on front of l_stack
                            l_stack.insert(0, char)
                            # then, go back on the m_stack to find a shorter match if there is one
                            while m_stack:
                                trs = [e.tr for e in m_stack]
                                matches = [c for c in combinations if list(c[0]) == trs]
                                if len(matches) == 1:
                                    # if one match, yield resulting char
                                    tr = matches[0][1] # get tr override from 2nd element of 'combinations' tuple
                                    connections = combineconnections([e.connections for e in m_stack])
                                    box = combineboxes([e.box for e in m_stack])
                                    script = m_stack[-1].script
                                    dist = m_stack[-1].dist
                                    # yield (tr, connections, script, box)
                                    yield Char(tr, connections, script, box, dist)
                                    m_stack.clear()
                                    continue
                                elif len(matches) > 1:
                                    raise ValueError('Too many matching combinations:', matches)
                                elif len(m_stack) > 1:
                                    # put last item back on front of l_stack
                                    l_stack.insert(0, m_stack.pop())
                                    continue
                                else:
                                    # yield last remaining char on m_stack,
                                    # so it won't be put on l_stack and start
                                    # an infinite loop
                                    yield(m_stack.pop())
                            continue

                        elif len(matches) > 1:
                            raise ValueError('Too many matching combinations:', matches)
                        else:
                            # successful match in matches[0]!
                            tr = matches[0][1] # get tr override from 2nd element of 'combinations' tuple
                            connections = combineconnections([e.connections for e in m_stack + [char]])
                            box = combineboxes([e.box for e in m_stack + [char]])
                            script = char.script
                            dist = char.dist
                            yield Char(tr, connections, script, box, dist)
                            m_stack.clear()
                            continue

            if char.tr.endswith('+') or char.tr in (c[0][0] for c in combinations):
                m_stack.append(char)
            else:
                yield char

    for e in m_stack:
        yield e
    m_stack.clear()
    yield Char('\n', (False, False), '', (0,0,0,0), 0)

def combineboxes(boxes):
    """Combine boxes

    Args:
        boxes: list of tuples: [(x1, y1, x2, y2)[, ...]]

    Returns:
        tuple with minimum values for xy1, maximum values for xy2

    Examples:
        >>> boxes = [(20, 2, 25, 4), (25, 1, 24, 8)]
        >>> combineboxes(boxes)
        (20, 1, 25, 8)
    """
    xy1 = [min(v) for v in zip(*[b[:2] for b in boxes])]
    xy2 = [max(v) for v in zip(*[b[2:] for b in boxes])]
    return tuple(xy1 + xy2)

def combineconnections(connections):
    """Combine tuples of boolean values with logical OR

    Args:
        connections: list of tuples: [(bool, bool)[, ...]]

    Returns:
        tuple: (bool, bool)

    Examples:
        >>> combineconnections([(True, False), (False, False)])
        (True, False)
        >>> combineconnections([(True, False), (False, True)])
        (True, True)

    """
    return tuple(any(x) for x in zip(*connections))

def add_spaces(chars, space_dist=15, finals='KMN', diacritics=DIACRITICS):
    """

    finals logic assumes two things:
    1. that final chars are upper case equivalent of normal lower case letter
       (to which it will be converted)
    2. that a final character can only occur in position 0 of a 'tr' string
    """
    space = Char(' ', None, None, None, None)
    prev_end = None
    for char in chars:
        c_left, c_right = char.connections
        x1, y1, x2, y2 = char.box
        tr = rstrip_diacr(char.tr, diacritics)
        if tr and tr[-1] in finals:
            char.tr = tr[:-1] + tr[-1].lower() + char.tr[len(tr):]
            prev_end = None
            yield space
        elif not c_left and prev_end is not None and x1 - prev_end >= space_dist:
            yield space
            prev_end = x2 if not c_right else None
        else:
            prev_end = x2 if not c_right else None
        # manual corrections for overlapping characters:
        # TODO this must be set in tables, or some other place
        if prev_end and char.tr.startswith("'"):
            prev_end -= 10
        elif prev_end and char.tr.startswith('g'):
            prev_end -= 20
        yield char

def rstrip_diacr(s, diacritics=DIACRITICS):
    stripped = False
    while True:
        for d in diacritics:
            if s.endswith(d):
                s = s[:-len(d)]
                stripped = True
                break
        if not stripped:
            break
        stripped = False
    return s

def fix_spaces(chars, spaces_file, letters=LETTERS, interpunction=INTERPUNCTION):
    space = Char(' ', None, None, None, None)

    with open(spaces_file, 'r') as f:
        spaces_lines = f.readlines()
    space_words = ((c for c in word if c in letters)
                   for line in spaces_lines
                   for word in line.split()[1:]
                   if any(c in letters for c in word))
    word = next(space_words)

    inscr_start = False
    for char in chars:
        if char.tr in ('<', '('):
            inscr_start = True
            yield space
            yield char
        elif inscr_start and char.tr in ('>', ')'):
            yield char
            yield space
            inscr_start = False
        elif inscr_start:
            # yield anything in inscriptio or header (i.e., between brackets),
            # including estimated spaces
            yield char
        elif char.tr == ' ':
            # discard estimated spaces
            continue
        elif char.script == '' and char.tr in interpunction:
            yield space
            yield char
        else:
            for c in char.tr:
                if c not in letters:
                    continue
                else:
                    try:
                        ch = next(word)
                    except StopIteration:
                        yield space
                        word = next(space_words)
                        ch = next(word)
                    if c != ch:
                        msg = (f'Characters do not match. '
                               f'Text: {c}; spaces_file: {ch}')
                        raise ValueError(msg)
            yield char

def flip_brackets(bracket, brackets=BRACKETS):
    pos = brackets.find(bracket)
    return brackets[pos - (pos%2 * 2 - 1)] # -1 if odd pos, +1 if even

def reverse_line(chars, brackets=BRACKETS):
    """Reverses a line of RTL text to read from LTR

    Reverses Syriac text, but not inline other text.
    The script is determined by the value 'script',
    which is an empty string for Syriac, and some
    other string value for other scripts, such as
    'r' for roman text and 'c' for cursive text.

    Arguments:
        chars: list of char tuples: [(tr, connections, script, box), ...]

    Yields:
        char tuples: (tr, connections, script, box)

    """
    stack = []
    chars = list(chars)
    while chars:
        char = chars.pop()
        if ((char.script != '' or (stack and char.tr == ' '))
                and char.tr not in brackets):
            stack.append(char)
            continue
        elif stack:
            while stack:
                yield stack.pop()
        if char.tr in brackets and len(char.tr) == 1:
            char.tr = flip_brackets(char.tr, brackets)
        yield char

def replace_dagger(chars):
    """Replaces dagger symbol '!' with dagger symbol '+'

    Originally, the dagger meta symbol was encoded with an exclamation mark.
    However, later texts use the exclamation mark as part of combined
    diacritics symbols (e.g. '^!'). So it is replaced with the plus symbol,
    which is otherwise only used in early stages of the OCR process to
    reconnect broken characters, and should not be present in the final
    text and not interfere with anything, especially since the dagger symbol
    always appears by itself surrounded by spaces, whereas the reconnecting
    plus is always connected to the broken character.

    TODO: replace the dagger exclamation mark in the tables files,
    so this temporary fix can be removed
    """
    for char in chars:
        if char.tr == '!':
            char.tr = '+'
        yield char

def replace_brackets(chars):
    """Replaces round brackets with angle brackets

    When round and angle brackets are so similar that they are
    not recognized as different characters by syrocr, the brackets
    surrounding Syriac text should be replaced by angle brackets.
    Round brackets always contain verse/chapter numbers in roman
    letters or digits, so brackets around Syriac characters must
    be angle brackets indicating in/subscriptions.
    This is relevant for Jeremiah/VTS 3.2
    """
    prev_char = None
    for char in chars:
        if prev_char is None:
            prev_char = char
            continue
        if prev_char.tr == '(' and char.script == '':
            prev_char.tr = '<'
        elif char.tr == ')' and prev_char.script == '':
            char.tr = '>'
        yield prev_char
        prev_char = char
    yield prev_char

def split_brackets(chars):
    """Splits non-Syriac multi-character transcriptions.

    Specifically for Lv.11:5 where '5' and ')' are connected,
    which upsets the verse splitting, which depends on
    unconnected brackets.
    """
    #TODO also split the box evenly over number of characters?
    for char in chars:
        if char.script != '' and len(char.tr) > 1:
            for c in char.tr:
                yield Char(c, char.connections, char.script, char.box, char.dist)
        else:
            yield char

def flip_yudh_sade(chars):
    """Flips yudh and Sade when in wrong order

    TODO they are in wrong order because Sade entirely
    overlaps the yudh. This should be fixed when using
    the 'center' of the character for ordering.
    """
    stack = None
    for char in chars:
        if stack is None:
            stack = char
            continue
        elif stack.tr.startswith('S') and stack.box[2] > char.box[2] and char.tr != '\n':
            # if previous char is 'S' which extends to right, beyond
            # current character: yield char and keep stack
            yield char
        else:
            yield stack
            stack = char
    if stack is not None:
        yield stack

def remove_meta(chars, meta=META):
    for char in chars:
        if char.tr not in meta:
            yield char

def remove_spaces(chars):
    for char in chars:
        char.tr = char.tr.replace(' ', '')
        yield char

def remove_interpunction(chars, interpunction=INTERPUNCTION):
    for char in chars:
        for symbol in interpunction:
            char.tr = char.tr.replace(symbol, '')
        yield char

def remove_diacritics(chars, diacritics=DIACRITICS):
    for char in chars:
        for symbol in diacritics:
            char.tr = char.tr.replace(symbol, '')
        yield char
