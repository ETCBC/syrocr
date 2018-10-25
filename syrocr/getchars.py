from .images import Im, BoundIm, AvgIm, getboundaries

def scanpage(source_image, lines, tables, verbose=False):
    im = Im(source_image)
    textlines = []
    for line in lines:
        if verbose:
            print('Line', line['num'], '...')
        textline = {'num': line['num'], 'type': line['type']}
        baseline = line['baseline']
        for section in ('main', 'marginl', 'marginr'):
            textline[section] = []
            if not line[section]:
                continue
            textsize = get_textsize(line['type'], section)
            table = tables[textsize]
            # end of last character, None if first or after connecting line
            # (this is to calculate character distance, for spacing)
            end = None
            for char, connecting_line in getcharacters(im, line[section], baseline):

                d = None if end is None else char.offset[0] - end
                end = None if connecting_line is not None else char.offset[0] + char.width
                x, y = char.offset
                box = (x, y, x + char.width, y + char.height)

                c = findchar(table, char, update_avgim=True, add_to_table=True)

                textline[section].append((c['id'], d, None, box))

        textlines.append(textline)

    return textlines, tables

def get_textsize(linetype, section):
    if section == 'main' and linetype in ('text', 'pagenr'):
        textsize = 'normal'
    else:
        textsize = 'small'
    return textsize

def findchar(table, char, update_avgim=True, add_to_table=True):
    # table is a list of dicts: {'id': c_id, 'avgim': avgim, 'key': key}
    if char.width >= 10:
        char = char.strip_connecting_line()
    found = False
    for c in table:
        offset = c['avgim'].compare(char.image(), char.baseline)
        if offset:
            found = c
            if update_avgim:
                c['avgim'].add(char.image(), char.baseline, offset)
            break
    if not found and add_to_table:
        found = addtochartable(table, char)
    return found

def addtochartable(table, char):
    # table is a list of dicts: {'id': c_id, 'avgim': avgim, 'key': key}
    entry = {
        'id': len(table),
        'avgim': AvgIm(char.image(), char.baseline),
        'key': None
        }
    table.append(entry)
    return entry

def getcharacters(im, box=None, baseline=None, overlaps=None):
    '''Generator object yielding characters'''
    # overlaps is a list of (as yet unimplemented) additional boundaries
    # that are outside the box area since they overlap with other elements
    # baseline

    # if type(im) is Image.Image:
    if type(im) is not Im:
        im = Im(im) # wrap PIL image in Im wrapper class

    if box is None:
        box = (0, 0, im.width, im.height)

    height = box[3] - box[1]
    offset = box[:2]

    # In order to make it easier to follow separate characters,
    # transform the image to a list of lists with pixel boundaries
    # per column.

    # TODO probably need to change this to implement overlapping areas
    relativebaseline = baseline - offset[1]
    boundim = im.crop(box).boundim(offset, relativebaseline)

    # First, isolate separate pixel groups, which can be characters,
    # parts of characters, diacritical points, or connected characters
    pixelgroups = separatepixelgroups(boundim)

    # Then, check if pixel groups consist of connected characters,
    # and if so, isolate the characters by splitting them on the
    # connecting line.
    splitchars = splitpixelgroups(pixelgroups)

    # Finally, find small pixel groups and try to reconnect them
    # to other groups that overlap with them vertically.
    # That should restore broken characters and connect diacritical
    # dots with their characters.
    characters = reconnectdots(splitchars)

    characters = reconnectbrokencharacters(characters)

    # return pixelgroups
    # return splitchars
    # return characters
    return sortcharacters(characters)


def separatepixelgroups(boundim):
    height = boundim.height
    baseline = boundim.baseline
    x, y = boundim.offset

    curgroups = []

    for i, bounds in enumerate(boundim.boundaries):

        # first, check which boundaries are connected to active characters,
        # keep the connected characters and move the unconnected ones to the 'chars' list
        prevgroups = curgroups
        curgroups = []
        for c in prevgroups:
            if any(connected(c.boundaries[-1], b) for b in bounds):
                c.addcolumn()       # add empty column to pixel group ...
                curgroups.append(c) # and append to curgroups
            else:
                # yield cropped(c)             # else yield finished pixel group
                yield c.cropped()             # else yield finished pixel group

        # then, for every boundary, check which active pixel groups are connected to it.
        for b in bounds:

            prevgroups = curgroups
            curgroups = []
            curgroup = None

            for c in prevgroups:

                if len(c.boundaries) > 1 and connected(c.boundaries[-2], b):
                    if curgroup is None:
                        c.addboundary(b)
                        curgroup = c
                    else:
#                         curgroup = combinechars(c, curgroup)
                        # curgroup = combineboundims(c, curgroup)
                        curgroup = c.combine(curgroup)
                else:
                    curgroups.append(c)
            if curgroup is None:
                curgroup = BoundIm(height, (x + i, y), None, baseline)
                curgroup.addboundary(b)
            curgroups.append(curgroup)

    # yield remaining pixel groups in the order they were added
    while curgroups:
        # yield cropped(curgroups.pop(0))
        yield curgroups.pop(0).cropped()

def splitpixelgroups(boundims, minsplitwidth=25, mincharheight=4):
    for boundim in boundims:
        baseline = boundim.baseline
        connectingbounds = getconnectingline2(boundim, c_height=6)
        if boundim.width < minsplitwidth or connectingbounds is None:
            connecting_line = None # TODO None to False
            yield (boundim, connecting_line)
            continue

        start, end = connectingbounds
        x, y = offset = boundim.offset
        height = boundim.height
        box = (0, start, boundim.width, end)

        def connectedabove(boundim):
            return boundim.offset[1] - y + boundim.height == start

        def connectedbelow(boundim):
            return boundim.offset[1] - y == end

        split_im = boundim.image() # get Im image of pixelgroup from BoundIm
        split_line = split_im.crop(box) # copy connecting line out of split_im
        split_im.paste(0, box) # delete connecting line from split_im

        # prepare BoundIm objects for split_im and split_line
        split_group = split_im.boundim(boundim.offset, baseline)
        group_line = split_line.boundim((x, start + y), baseline - start)

        subgroups = list(separatepixelgroups(split_group))
        for i, subgroup in enumerate(subgroups):
            if subgroup is None:
                continue
            if subgroup.height < mincharheight and (connectedabove(subgroup) or connectedbelow(subgroup)):
                group_line = group_line.combine(subgroup)
                subgroups[i] = None
            else:
                for j, cmpgroup in enumerate(subgroups[i+1:]):
                    if cmpgroup is None:
                        continue
                    xa1, xa2 = subgroup.offset[0], subgroup.offset[0] + subgroup.width
                    xb1, xb2 = cmpgroup.offset[0], cmpgroup.offset[0] + cmpgroup.width
                    opposites = ((connectedabove(subgroup) and connectedbelow(cmpgroup)) or
                                  connectedabove(cmpgroup) and connectedbelow(subgroup))
                    if (overlap((xa1, xa2), (xb1, xb2)) and opposites):
                        subgroups[i] = subgroup.combine(cmpgroup)
                        subgroups[i+1+j] = None

        subgroups = [group for group in subgroups if group is not None]

        for i, subgroup in enumerate(subgroups):
            connecting_line = True
            x1 = subgroup.offset[0] - split_group.offset[0]
            x2 = x1 + subgroup.width
            # if first or last group, do not cut off extending connecting line
            if i == 0:
                x1 = 0
            if i == len(subgroups) - 1:
                x2 = split_group.width
                connecting_line = None
            yield (subgroup.combine(group_line.slice(x1,x2)), connected)

def getconnectingline2(boundim, c_height=6):
    """Find top and bottom edge of connecting line.

    Search around boundim.baseline for the rows with the highest
    number of pixels. The value of c_height determines the number
    of rows to consider, as well as the area to search in (being
    between boundim.baseline - c_height and boundim.baseline + c_height)

    Args:
        boundim (BoundIm): a BoundIm image object
        c_height (int): height of the connecting line in pixel rows

    Returns:
        tuple (int, int): top and bottom edge value of connecting line

    """
    # first get total number of pixels per horizontal row
    rows = boundim.image().rows()
    px_per_row = [sum([bool(p) for p in row]) for row in rows]

    # set initial value for top of connecting line,
    # from which to search downward
    c_start = max(boundim.baseline - c_height, 0)

    # initialize values
    max_total = 0
    max_start = c_start

    # loop
    while c_start <= boundim.baseline and c_start + c_height <= boundim.height:
        c_end = c_start + c_height
        total_px = sum(px_per_row[c_start:c_end])
        if total_px >= max_total:
            max_total = total_px
            max_start = c_start
        c_start += 1
    return max_start, min(max_start + c_height, boundim.height)

# getconnectingline(): DEPRECATED
# in favour of getconnectingline2()
def getconnectingline(boundim, maxheight=6):
    rows = boundim.image().rows()
    maxlengths = [max([e-s for s,e in getboundaries(row)]) for row in rows]
    avgmaxlen = sum(maxlengths)/len(maxlengths)
    # in case maxheight=6:
    # connecting line can be at most 6 pixels high
    # and should overlap with baseline: so look only
    # at the range from baseline-6 to baseline+6
    search_start = max(boundim.baseline - maxheight, 0) # make sure it is not negative
    search_end = boundim.baseline + maxheight
    start, end = None, None
    for i, maxlength in enumerate(maxlengths[search_start:search_end]):
        is_connecting_line = (maxlength > (avgmaxlen * 2))
        row_nr = i + search_start
        if is_connecting_line:
            if start is None:
                start = row_nr
            end = row_nr + 1
    if start is None:
        return None
    else:
        # add row with longest maxlength until maxheight reached
        while end - start < maxheight:
            if len(maxlengths) > end and maxlengths[end] >= maxlengths[start-1]:
                end += 1
            else:
                start -= 1
        return start, end

# splitpixelgroup(): DEPRECATED
# in favour of splitpixelgroups (check for obsolete helper functions)
def splitpixelgroup(boundim, baseline=None):
    '''
    Split a pixel group into characters on the connecting line

    Returns a generator of tuples with two elements.
    The first is a character, the second a connecting line part or None.
    '''
    # TODO: make pixel distances relative to dpi

    # First get the baseline of the image.
    # This value should be the distance in pixels
    # of the baseline from the top of boundim.
    # If it is not set in boundim and not given
    # as an argument, it is determined by the
    # getxheight() method.

    if baseline is None:
        raise ValueError('No baseline provided')
        # TODO getxheight() is in getlines.py, not available here
        # if boundim.baseline is None:
        #     baseline, xheight = getxheight(boundim.image(), stoponfirstbaseline=True)
        # else:
        #     baseline = boundim.baseline

    # some values:
    # maximum height of the connecting line
    maxheight = 6

    # maximum deviation from the baseline.
    # bottom of the connecting line should not be more than # pixels above baseline
    # the top should not be less than # pixels above the baseline
    maxdeviation = 4

    # minimum height for a column to trigger passedchar
    charheight = 10

    # minimum length for a connecting line for splitting characters
    minconnect = 10

    # We need to keep track of two types of connecting lines:
    # - free connecting line, (with no other boundaries below or above)
    # - closed connecting line, (with other boundaries below or above)
    startfree, endfree, startclosed, endclosed = None, None, None, None
    passedchar = False
    newoffset = 0

    for i, col in enumerate(boundim.boundaries):
        # check if this is an open connection line
        start, end = col[0][0], col[-1][1]
        if passedchar:
            if checkconnectingline(start, end, baseline, maxheight, maxdeviation):
                if startfree is None:
                    startfree = i
            else:
                if startfree is not None and endfree is None:
                    endfree = i
            if any(checkconnectingline(b[0], b[1], baseline, maxheight, maxdeviation) for b in col):
                if startclosed is None:
                    startclosed = i
            else:
                if startclosed is not None and endclosed is None:
                    if i - startclosed > minconnect:
                        endclosed = i
                    else:
                        startfree, endfree, startclosed, endclosed = None, None, None, None
#         if any(b[1] - b[0] > charheight for b in col):
        if col[-1][1] - col[0][0] > charheight:
#             if passedchar and endfree is not None:
            if (passedchar and endfree is not None and
                (endclosed if endclosed is not None else i) - startclosed > minconnect):
                # go split character on free connecting line
                # make new BoundIm for the part to be separated
                # and another one for the connecting line
                # yield cropped(boundim.slice(newoffset, startfree)), cropped(boundim.slice(startfree, endfree))
                yield boundim.slice(newoffset, startfree).cropped(), boundim.slice(startfree, endfree).cropped()
                newoffset = endfree
                startfree, endfree, startclosed, endclosed = None, None, None, None
                passedchar = False
            else:
                passedchar = True
    yield boundim.slice(newoffset, boundim.width).cropped(), None


def checkconnectingline(start, end, baseline, maxheight, maxdeviation):
    return (end - start < maxheight and # if not too high
            end < baseline + maxdeviation and
            start > baseline - maxdeviation - maxheight)

def reconnectdots(splitchars, min_size=4):
    '''Reconnect diacritical dots with their characters and restore broken characters'''

    smallgroups = []

    prevgroup = None

    for group in splitchars:

        # discard very very small groups
        if group[0].width * group[0].height <= min_size:
            continue

        # the only reason there is a 'prevgroup', is that a small part may be broken off.
        # If that is so, reconnect, and then yield the previous group.
        if (prevgroup is not None and issmallgroup(group) and
            connectedwithgap(prevgroup[0], group[0]) and
            # check if less than half the pixels of the group area is black,
            # which often means it is a broken off line segment
            sum(b[1]-b[0] for col in group[0].boundaries for b in col) < group[0].width*group[0].height/2
        ):
            # group = (combineboundims(group[0], prevgroup[0]), prevgroup[1])
            group = (group[0].combine(prevgroup[0]), prevgroup[1])
            prevgroup = None

        # elif prevgroup is not None:
        #     yield prevgroup

        if issmallgroup(group):
            # print(group[0], prevgroup[0])
            if prevgroup is not None:
                smallgroup = group[0]
                baselinedist = smallgroup.baseline - smallgroup.height
                sectiondist = getsectiondist(smallgroup, prevgroup[0])
            if (
                prevgroup is not None
                # small group starts before prevgroup ends
                and smallgroup.offset[0] < prevgroup[0].offset[0] + prevgroup[0].width
                and (
                # is smallgroup is more than (say) 10px above the baseline,
                # it should be less than that distance above the top of the
                # section of the overlapping character
                    (baselinedist > 10 and sectiondist < baselinedist)
                # if it is not, it should be below the top of the section
                # of the overlapping character
                    or (baselinedist < 10 and 0 > sectiondist > -12)
                )
            ):
                prevgroup = (prevgroup[0].combine(smallgroup), prevgroup[1])
            else:
                smallgroups.append(group[0])

        else:
            prevsmallgroups = smallgroups
            smallgroups = []
            prevsmallgroup = None

            for smallgroup in prevsmallgroups:
                # baselinedist is the distance between the baseline and
                # the bottom of the smallgroup
                # print(smallgroup, group[0])
                baselinedist = smallgroup.baseline - smallgroup.height
                sectiondist = getsectiondist(smallgroup, group[0])
                # if the small group ends before the current group starts (no overlap):
                if smallgroup.offset[0] + smallgroup.width <= group[0].offset[0]:
                    # print(smallgroup, group[0], 'first')
                    # if the small group overlaps with the previous small group, combine them
                    if (prevsmallgroup is not None and # (even if they are only very close)
                        prevsmallgroup.offset[0] + prevsmallgroup.width + 2 >= smallgroup.offset[0]):
                        # smallgroup = combineboundims(prevsmallgroup, smallgroup)
                        smallgroup = prevsmallgroup.combine(smallgroup)
                    # if they don't overlap, yield the previous small group
                    elif prevsmallgroup is not None:
                        yield (prevsmallgroup, None)
                    # update prevsmallgroup to current small group
                    prevsmallgroup = smallgroup
                # if the small group does overlap with the current group, combine them
#                 elif smallgroup.offset[0] + smallgroup.width <= group[0].offset[0] + group[0].width:
                elif (
                    smallgroup.offset[0] < group[0].offset[0] + group[0].width
                    and (
                    # is smallgroup is more than (say) 10px above the baseline,
                    # it should be less than that distance above the top of the
                    # section of the overlapping character
                        (baselinedist > 10 and sectiondist < baselinedist)
                    # if it is not, it should be below the top of the section
                    # of the overlapping character
                        or (baselinedist < 10 and 0 > sectiondist > -12)
                    )
                ):
                    # print(smallgroup, '2nd')
                    # group = (combineboundims(group[0], smallgroup), group[1])
                    group = (group[0].combine(smallgroup), group[1])
                # if there is no overlap and small group comes after current group,
                # put it back on the stack
                else:
                    # print(smallgroup, '3rd')
                    smallgroups.append(smallgroup)
            # if prevsmallgroup contains a small group, yield it
            if prevsmallgroup is not None:
                yield (prevsmallgroup, None)

            if prevgroup is not None:
                yield prevgroup
            prevgroup = group

    if prevgroup is not None:
        yield prevgroup

    # if there are any remaining smallgroups, yield those in order
    while smallgroups:
        yield (smallgroups.pop(0), None)

def getsectiondist(smallgroup, group):
    if not overlap((smallgroup.offset[0], smallgroup.offset[0]+smallgroup.width-1), (group.offset[0], group.offset[0]+group.width-1)):
        return None
    # take a section of the character overlapping with the small group
    section = getsection(smallgroup, group)
    # sectiondist is the distance between the smallgroup and the section
    sectiondist = section.offset[1] - (smallgroup.offset[1] + smallgroup.height)
    # correct sectiondist if smallgroup is below the section
    # by removing heights of both groups
    if sectiondist < 0:
        sectiondist = sectiondist + smallgroup.height + section.height
    return sectiondist

def getsection(smallgroup, group):
    start = max(smallgroup.offset[0], group.offset[0]) - group.offset[0]
    end = min(smallgroup.offset[0] + smallgroup.width, group.offset[0] + group.width) - group.offset[0]
    return group.slice(start, end).cropped()

#         # start and end of current pixel group
#         grouprange = (group[0].offset[0] - 1, group[0].offset[0] + group[0].width)

#         issmall =

#         for prevgroup in prevgroups:

#             prevrange = (prevgroup[0].offset[0] - 1, prevgroup[0].offset[0] + prevgroup[0].width)

#             # first check if small dot is a broken off remainder of the previous character
#             # and if so, combine with previous character
#             if issmallgroup(group) and connectedwithgap(prevgroup[0], group[0]):
#                 group = (combineboundims(group[0], prevgroup[0]),
#                          group[1] if group[1] is not None else prevgroup[1])

#             # otherwise, check if the previous small group overlaps with the current
#             # (small or not small) group, and if so, combine
#             elif issmallgroup(prevgroup) and overlap(prevrange, grouprange):
#                 group = (combineboundims(group[0], prevgroup[0]),
#                          group[1] if group[1] is not None else prevgroup[1])

#             # if both prevgroup and the current group are small pixel groups,
#             # keep both so they may be combined with the same character
#             # (such as seyame)
#             elif issmallgroup(prevgroup) and issmallgroup(group):
#                 curgroups.append(prevgroup)

#             # if the previous group starts after the end of the current
#             # group (as with diacritical dots connected to characters
#             # that were split after the dot was separated), keep the group
#             elif issmallgroup(prevgroup) and prevrange[0] > grouprange[1]:
#                 curgroups.append(prevgroup)

#             # if none of these things is the case, yield the previous
#             # (completed character) pixel group, and keep the current group
#             else:
#                 yield prevgroup

#         curgroups.append(group)

#     while curgroups:
#         yield curgroups.pop(0)

def connectedwithgap(prevgroup, group, maxgap=2):
    # if the last boundary of the prevgroup is not more than maxgap
    # pixels away from the horizontal offset of group, check for overlap
    if group.offset[0] - (prevgroup.offset[0] + prevgroup.width) > maxgap:
        return False
    else:
        # in order to compare boundaries of different groups, get the absolute values
        groupbounds = [
            (b[0] + group.offset[1], b[1] + group.offset[1])
            for b in group.boundaries[0]
        ]
        prevbounds = [
            (b[0] + prevgroup.offset[1], b[1] + prevgroup.offset[1])
            for b in prevgroup.boundaries[-1]
        ]
        return any(connected(prevbounds, b, gap=maxgap) for b in groupbounds)

def issmallgroup(group):
    '''Check whether grouptuple[0] is smaller than 144 pixels and grouptuple[1] is None'''
    top = min(b[0] for col in group[0].boundaries for b in col)
    bot = max(b[1] for col in group[0].boundaries for b in col)
    height = bot - top
    return group[0].width * height < 144 and group[1] is None

def overlap(range1, range2):
    """Does the range (start1, end1) overlap with (start2, end2)?"""
    (start1, end1), (start2, end2) = range1, range2
    return end1 >= start2 and end2 >= start1

def connected(columnbounds, bound, gap=0):
    '''Is any of columnbounds connected to (=overlapping with) bound?'''
    return any(overlap(cb, (bound[0] - gap, bound[1] + gap)) for cb in columnbounds)

def reconnectbrokencharacters(chars):
    """Connect overlapping characters

    If they overlap for at least the distance
    of half the width of the narrowest one"""
    # TODO check for distance
    prevchar = None

    for char in chars:

        if prevchar is None:
            prevchar = char
            continue

        b1 = prevchar[0].offset[0], prevchar[0].offset[0] + prevchar[0].width
        b2 = char[0].offset[0], char[0].offset[0] + char[0].width
        # make sure b1 contains narrowest character
        b1, b2 = sorted([b1, b2], key=lambda x: x[1]-x[0])
        # calculate overlap amount
        # https://stackoverflow.com/a/6821298
        overlap = min(b1[1], b2[1]) + 1 - max(b1[0], b2[0])
        # check if overlap is at least as much as half the narrower character
        if (overlap > ((b1[1] - b1[0]) / 2)
            # TODO hackish way to prevent long tsade and nun
            # characters to combine with overlapping characters.
            # Should properly be done by checking proximity.
            and b2[1] - b2[0] < 20
           ):
            connecting_line = prevchar[1] if prevchar[1] is not None else char[1]
            yield (prevchar[0].combine(char[0]), connecting_line)
            prevchar = None
        else:
            yield prevchar
            prevchar = char

    if prevchar is not None:
        yield prevchar

def sortcharacters(chars):
    '''Sort characters back in right order

    after having been misplaced by previous algorithms'''
    # stack = []
    # for char in chars:
    return sorted(chars, key=lambda x: x[0].offset[0])
