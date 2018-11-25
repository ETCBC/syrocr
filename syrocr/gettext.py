import os
import json

def verses(*args, inscr=True, spaces_file=None, **kwargs):
    """Get text verse tuples"""
    chars = get_text(*args, **kwargs)
    if spaces_file is not None:
        chars = fix_spaces(chars, spaces_file=spaces_file)
    return chars_to_verses(chars, inscr=inscr)

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
    for tr, connections, script, box in chars:
        if tr == '(':
            yield join_verse(tag, text)
            tag.clear()
            text.clear()
            tag_start = True
            tag.append(tr)
        elif tag_start and tr == ')':
            tag.append(tr)
            tag_start = False
        elif tag_start:
            tag.append(tr)
        elif tr == '<':
            inscr_start = True
            inscr_txt.append(tr)
        elif inscr_start and tr == '>':
            inscr_txt.append(tr)
            inscr_start = False
        elif inscr_start:
            inscr_txt.append(tr)
        else:
            if tr != ' ' and inscr_txt:
                if inscr:
                    text.extend(inscr_txt)
                inscr_txt.clear()
            text.append(tr)
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
    with open(tables_filename, 'r') as f:
        tables = json.load(f)
    # TODO for now we only look at line type 'text',
    # there section 'main', which has always textsize 'normal'.
    # This should be properly set in an argument.
    table = tables['normal']

    with os.scandir(json_textlines_dir) as sd:
        filenames = sorted(f.path for f in sd
            if f.is_file() and f.name.endswith(json_texline_ext))
    for filename in filenames:
        basename = os.path.basename(filename)[:-len(json_texline_ext)]
        with open(filename, 'r') as f:
            textlines = json.load(f)

        for textline in textlines:
            # TODO for now we only look at line type 'text',
            # there section 'main'. This should be set in an argument.
            if textline['type'] != 'text':
                continue
            chars = get_textline(table, textline['main'], basename,
                textline['num'], combinations, corrections)

            # SOME FIXES TODO MUST BE FIXED IN OTHER WAYS
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
        l_stack.append(entry)
        while l_stack:
            entry = l_stack.pop(0)
            c_id, connections, keyoverride, box = entry
            tr = table[c_id]['key']['tr']
            script = table[c_id]['key']['script']
            dist = table[c_id]['key']['dist']

            # discard entries with empty translation:
            if tr == '':
                continue
            elif m_stack:
                # if there are items on the m_stack, check combinations
                pos = 0
                tr1 = table[m_stack[pos][0]]['key']['tr']
                if len(m_stack) == 1 and tr1[-1] == '+' and tr[0] == '+' and tr1[:-1] == tr[1:]:
                    # combine split characters such as 'T+', '+T'
                    new_tr = tr[1:]
                    new_connections = [m_stack[0][1][0], entry[1][1]]
                    new_box = combineboxes([m_stack[0][3], entry[3]])
                    yield (new_tr, new_connections, script, new_box)
                    m_stack.clear()
                    continue
                else:
                    # copy combinations, to select matching combinations
                    matches = combinations
                    while len(m_stack) > pos:
                        tr1 = table[m_stack[pos][0]]['key']['tr']
                        matches = [c for c in matches if (len(c[0]) > pos and c[0][pos] == tr1)]
                        pos += 1
                    if not matches:
                        raise ValueError('Stack contains unmatched entry.')
                    elif [c for c in matches if (len(c[0]) > pos + 1 and c[0][pos]) == tr]:
                        # there are matching combinations with more members than current,
                        # so add current entry to m_stack:
                        m_stack.append(entry)
                        continue
                    else:
                        matches = [c for c in matches if (len(c[0]) > pos and c[0][pos]) == tr]
                        if not matches:
                            # print('BLAA', len(m_stack), m_stack)
                            # first, put current entry back on l_stack
                            l_stack.insert(0, entry)
                            # then, go back on the m_stack to find a shorter match if there is one
                            while m_stack:
                                # print('stack length:', len(m_stack), m_stack)
                                trs = [table[e[0]]['key']['tr'] for e in m_stack]
                                matches = [c for c in combinations if list(c[0]) == trs]
                                if len(matches) == 1:
                                    new_tr = matches[0][1] # get tr override from 2nd element of 'combinations' tuple
                                    new_connections = combineconnections([e[1] for e in m_stack])
                                    new_box = combineboxes([e[3] for e in m_stack])
                                    yield (new_tr, new_connections, script, new_box)
                                    m_stack.clear()
                                    continue
                                elif len(matches) > 1:
                                    raise ValueError('Too many matching combinations:', matches)
                                elif len(m_stack) > 1:
                                    # put last item back on l_stack
                                    l_stack.insert(0, m_stack.pop())
                                    continue
                                else:
                                    # if one entry left on stack (the first
                                    # one, which started matching a
                                    # combination) -- break out of the loop
                                    break

                            # if only one item is left on m_stack, yield it
                            # so we won't end in infinite loop
                            for e in m_stack:
                                new_tr = table[e[0]]['key']['tr']
                                for c, override in corrections:
                                    if basename == c[0] and line_num == c[1] and i - len(l_stack) == c[2] and e[0] == c[3]:
                                        new_tr = override
                                        break
                                if new_tr == '':
                                    continue
                                # print('inEND', m_stack)
                                new_connections = e[1]
                                new_box = e[3]
                                yield (new_tr, new_connections, script, new_box)
                            m_stack.clear()
                            continue

                            # # if no match, yield entries on m_stack, **but not** current entry;
                            # # and do **not** continue to next entry: first check if current
                            # # entry needs to be put on the m_stack
                            # for e in m_stack:
                            #     new_tr = table[e[0]]['key']['tr']
                            #     new_connections = e[1]
                            #     new_box = e[3]
                            #     yield (new_tr, new_connections, script, new_box)
                            # m_stack.clear()
                        elif len(matches) > 1:
                            raise ValueError('Too many matching combinations:', matches)
                        else:
                            # successful match in matches[0]!
                            new_tr = matches[0][1] # get tr override from 2nd element of 'combinations' tuple
                            new_connections = combineconnections([e[1] for e in m_stack + [entry]])
                            new_box = combineboxes([e[3] for e in m_stack + [entry]])
                            yield (new_tr, new_connections, script, new_box)
                            m_stack.clear()
                            continue

            if tr[-1] == '+' or tr in (c[0][0] for c in combinations):
                m_stack.append(entry)
            else:
                # TODO this could be optimized by filtering corrections at page and line level
                for c, override in corrections:
                    if basename == c[0] and line_num == c[1] and i - len(l_stack) == c[2] and c_id == c[3]:
                        tr = override
                        break
                if tr == '':
                    continue
                yield (tr, connections, script, box)

    for e in m_stack:
        c_id, connections, keyoverride, box = e
        tr = table[c_id]['key']['tr']
        script = table[c_id]['key']['script']
        yield (tr, connections, script, box)
    m_stack.clear()

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
    # boxes = [c[3] for c in chars]
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

def add_spaces(chars, space_dist=15, final_chars='KMN', diacr='#^"'):
    """

    final_chars logic assumes two things:
    1. that final chars are upper case equivalent of normal lower case letter
       (to which it will be converted)
    2. that a final character can only occur in position 0 of a 'tr' string
    """
    space = (' ', None, None, None)
    prev_end = None
    for tr, connections, script, box in chars:
        c_left, c_right = connections
        x1, y1, x2, y2 = box
        if tr.rstrip(diacr)[-1] in final_chars:
            yield space
            prev_end = None
            tr = ''.join([c.lower() if c in final_chars else c for c in tr])
            # tr = tr[:-1] + tr[-1].lower()
        elif not c_left and prev_end is not None and x1 - prev_end >= space_dist:
            yield space
            prev_end = x2 if not c_right else None
        else:
            prev_end = x2 if not c_right else None
        # manual corrections for overlapping characters:
        # TODO this must be set in tables, or some other place
        if prev_end and tr[0] == '\'':
            prev_end -= 10
        elif prev_end and tr[0] == 'g':
            prev_end -= 20
        yield (tr, connections, script, box)

def fix_spaces(chars, spaces_file):
    space = (' ', None, None, None)
    letters = list('\'bgdhwzHTyklmns`pSqr$t')
    interpunction = ('*', 'o', '=.', '=:', '^.')

    with open(spaces_file, 'r') as f:
        spaces_lines = f.readlines()
    space_words = ((c for c in word if c in letters)
                   for line in spaces_lines
                   for word in line.split()[1:]
                   if any(c in letters for c in word))
    word = next(space_words)

    inscr_start = False
    for tr, connections, script, box in chars:
        if tr in ('<', '('):
            inscr_start = True
            yield space
            yield (tr, connections, script, box)
        elif inscr_start and tr in ('>', ')'):
            yield (tr, connections, script, box)
            yield space
            inscr_start = False
        elif inscr_start:
            # yield anything in inscriptio or header (i.e., between brackets),
            # including estimated spaces
            yield (tr, connections, script, box)
        elif tr == ' ':
            # discard estimated spaces
            continue
        elif script == '' and tr in interpunction:
            yield space
            yield (tr, connections, script, box)
        else:
            for c in tr:
                if c not in letters:
                    continue
                else:
                    try:
                        char = next(word)
                    except StopIteration:
                        yield space
                        word = next(space_words)
                        char = next(word)
                    if c != char:
                        msg = (f'Characters do not match. '
                               f'Text: {c}; spaces_file: {char}')
                        raise ValueError(msg)
            yield (tr, connections, script, box)

def flip_brackets(bracket, brackets='<>()'):
    pos = brackets.find(bracket)
    return brackets[pos - (pos%2 * 2 - 1)] # -1 if odd pos, +1 if even

def reverse_line(chars, brackets='<>()'):
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
        tr, connections, script, box = chars.pop()
        if (script != '' or (stack and tr == ' ')) and tr not in brackets:
            stack.append((tr, connections, script, box))
            continue
        elif stack:
            while stack:
                yield stack.pop()
        if tr in brackets and len(tr) == 1:
            tr = flip_brackets(tr, brackets)
        yield (tr, connections, script, box)

def flip_yudh_sade(chars):
    """Flips yudh and Sade when in wrong order

    TODO they are in wrong order because Sade entirely
    overlaps the yudh. This should be fixed when using
    the 'center' of the character for ordering.
    """
    stack = None
    for char in chars:
        tr, connections, script, box = char
        if stack is None:
            stack = char
            continue
        elif stack[0] and stack[0][0] == 'S' and stack[3][2] > box[2]:
            # if previous char is 'S', which extends to right beyond
            # current character: yield char and keep stack
            yield char
        else:
            yield stack
            stack = char
    yield stack

# def get_text_chars(json_textlines_dir, tables_filename,
#         combinations=None, corrections=None, json_texline_ext='_textlines.json',
#         meta=False, interp=True, diacr=True, spaces=True):
def filter_chars(chars, meta=False, interp=True, diacr=True):
    """
    Yields:
        pass
    """
    # chars = get_text2(json_textlines_dir, tables_filename,
    #                   combinations, corrections, json_texline_ext)
    if not meta:
        chars = remove_meta(chars)
    if not interp:
        chars = remove_interpunction(chars)
    if not diacr:
        chars = remove_diacritics(chars)
    return chars

def remove_meta(chars, meta='!|-'):
    for tr, connections, script, box in chars:
        tr = ''.join([c for c in tr if c not in meta])
        yield (tr, connections, script, box)

def remove_spaces(chars):
    for tr, connections, script, box in chars:
        tr = tr.replace(' ', '')
        yield (tr, connections, script, box)

def remove_interpunction(chars, interpunction=('=:','=.', '=/', '=\\','^\\','^.','o','*')):
    for tr, connections, script, box in chars:
        for symbol in interpunction:
            tr = tr.replace(symbol, '')
        yield (tr, connections, script, box)

def remove_diacritics(chars, diacritics='#^"'):
    for tr, connections, script, box in chars:
        tr = ''.join([c for c in tr if c not in diacritics])
        yield (tr, connections, script, box)
