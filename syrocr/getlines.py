from .images import Im, getboundaries

# TODO make consistent use of constants, or not at all
MAXLINEHEIGHT = 1/4 # If lineheight is higher than 1/4 inch (75px@300dpi),
                    # check if overlapping lines must be split
# LINEDIST_TEXT = 1/4 # standard line spacing is 1/4 inch (75px@300dpi)
LINEDIST_TEXT = 1/3.75 # standard line spacing is 1/3.75 inch (80px@300dpi) #TODO should be argument
LINEDIST_APP = 2/11 # 2/11 inch (ca. 54px@300dpi, 4.6181818 mm)


def getlines(filename, dpi=None, verbose=False):
    '''Scan a page and return a list of line objects'''
    im = Im(filename, dpi)
    lines = []
    for b in getlineboundaries(im, verbose=verbose):
        box = (0, b[0], im.width, b[1])
        line = Line(lines, im, box)
        if verbose:
            print(line)
        lines.append(line)
    lines = replacecolumnlines2(im, lines, verbose=verbose)

    maincol = findmaincolumn(lines)

    return linestodict2(lines, maincol)

def linestodict2(lines, maincol):
    import json
    dictlines = []
    for line in lines:
        dictline = {'num': line.num,
                    'type': line.type,
                    'baseline': line.baseline,
                    'main': mergeboxes(line.elements),
                    'marginl': None,
                    'marginr': None}
        dictlines.append(dictline)
    return dictlines

def linestodict(lines, maincol):
    import json
    dictlines = []
    l, r = maincol
    for line in lines:
        dictline = {'num': line.num,
                    'type': line.type,
                    'baseline': line.baseline,
                    'main': None,
                    'marginl': None,
                    'marginr': None}
        bbox = []
        marginl = []
        marginr = []
        for x1, y1, x2, y2 in line.elements:
            if x2 < l:
                marginl.append((x1, y1, x2, y2))
            elif x1 > r:
                marginr.append((x1, y1, x2, y2))
            else:
                bbox.append((x1, y1, x2, y2))
        dictline['main'] = mergeboxes(bbox)
        if marginl:
            dictline['marginl'] = mergeboxes(marginl)
        if marginr:
            dictline['marginr'] = mergeboxes(marginr)

        dictlines.append(dictline)

    return dictlines

def replacecolumnlines2(im, lines, verbose=False):
    # first line is either centered pagenumber,
    # or justified page header
    header_width = lines[0].bbox[2] - lines[0].bbox[0]
    center = lines[0].bbox[0] + (header_width//2)
    # gap = (center - 75, center + 75)
    # hasgap = lambda line: not any(overlap((e[0], e[2]), gap, -10) for e in line.elements)
    # def hasgap(elements, gap=gap):
    #     return not any(overlap((e[0], e[2]), gap, -10) for e in line.elements)

    columnlines = []
    newlines = []
    start = False

    for i, line in enumerate(lines):
        if line.type == 'text' and line.hascolumngap(center, gapwidth=90):
            # gapwidth is actually about 150 pixels, but not always centered
            columnlines.append(line)
            if not start:
                start = i
        elif columnlines:
            break

    if not columnlines:
        return lines

    if verbose:
        print(f'Replacing lines {start} to {start+len(columnlines)}...')

    newlines = lines[:start]

    x1,y1,x2,y2 = mergeboxes(line.bbox for line in columnlines)

    linepart = None
    for box in (im.getbbox((center,y1,x2,y2)), im.getbbox((x1,y1,center,y2))):
        for b in getlineboundaries(im, box):
            linebox = im.getbbox((box[0], b[0], box[2], b[1]))
            if linepart: # merge smaller separated parts with next line
                linebox = mergeboxes((linepart, linebox))
                linepart = None
            elif linebox[2] - linebox[0] < 450:
                linepart = linebox
                linebox = None
            if linebox is not None:
                newlines.append(Line(newlines, im, linebox, linetype='column'))
                if verbose:
                    print(newlines[-1])
        if linepart:
            newlines.append(Line(newlines, im, linepart, linetype='column'))
            linepart = None
            if verbose:
                print(newlines[-1])

    if verbose:
        print('Adding updated last lines...')
    # add lines after 'apparatus2' with updated line numbers
    for line in lines[start+len(columnlines):]:
        line.num = len(newlines)
        newlines.append(line)

        if verbose:
            print(newlines[-1])

    return newlines

def replacecolumnlines(im, lines, verbose=False):
    '''Split two column lines of type 'apparatus2' '''

    l_m, r_m = findmaincolumn(lines)
    center = (r_m-l_m)//2+l_m

    columnlines = []
    newlines = []
    start = None
    for i, line in enumerate(lines):
        if line.type == 'apparatus2' and line.hascolumngap(center):
            columnlines.append(line)
            if not start:
                start = i
        elif columnlines:
            break

    if not columnlines:
        return lines

    if verbose:
        print(f'Replacing lines {start} to {start+len(columnlines)}...')

    newlines = lines[:start]

    x1,y1,x2,y2 = mergeboxes(line.bbox for line in columnlines)

    for box in (im.getbbox((x1,y1,center,y2)), im.getbbox((center,y1,x2,y2))):
        for b in getlineboundaries(im, box):
            linebox = (box[0], b[0], box[2], b[1])
            newlines.append(Line(newlines, im, linebox, linetype='apparatus2'))

            if verbose:
                print(newlines[-1])

    if verbose:
        print('Adding updated last lines...')
    # add lines after 'apparatus2' with updated line numbers
    for line in lines[start+len(columnlines):]:
        line.num = len(newlines)
        newlines.append(line)

        if verbose:
            print(newlines[-1])

    return newlines

def mergeboxes(boxes):
    return tuple(min(x) if i<2 else max(x) for i,x in enumerate(zip(*boxes)))

def getlineboundaries(im, box=None, mindist = 5, minheight = 10, verbose=False):
    # TODO set values relative to dpi
    # get vertical boundaries, and connect accidentally
    # separated lines such as when dots below the line
    # are seen as separate line
    if box is None:
        box = im.getbbox()
    prevb = None

    x1, y1, x2, y2 = box
    # first, get all boundaries separated by at least one line of white pixels
    for bounds in getboundaries(im.rows(box), y1):
        # then try to split lines that are higher than MAXLINEHEIGHT
        for start, end in splitlineboundaries(im, bounds, verbose=verbose):
            # finally, try to combine too low lines with only e.g. dots
            if prevb and end-start<minheight:
                if start-prevb[1]<mindist:
                    prevb = (prevb[0], end)
                else:
                    pass # ignore small and isolated dots
            else:
                if prevb:
                    yield prevb
                prevb = (start, end)
    yield prevb

def splitlineboundaries(im, bounds, maxheight=MAXLINEHEIGHT, verbose=False):
    # vts-044_2L.tif: many overlapping lines.
    # TODO: find overlapping area by following pixels
    # for large boundaries
    # TODO: this can probably be done MUCH simpler
    # print('boundaries: {}'.format(bounds))


    if len(bounds) == 2:
        top, bot = bounds
        x1, y1, x2, y2 = box = im.getbbox((0,top,im.width,bot))
    else:
        x1, y1, x2, y2 = box = bounds

    if y2-y1 < im.dpi[0]*maxheight:
        yield (y1,y2)
        return

    td, rowdens = getdensity(im, box)
    rows = im.rows(box)
    start, end = y1, None
    foundx, pastx = False, False
    prevbounds = None
    line, nextline = tuple(), tuple()

    for (y, rd), row in zip(rowdens, rows):
        # print(rd/td)            #DEBUG
        # DEBUG
        # To decide what is a 'line', we look for an 'x' area. That is the
        # part of a line with the highest amount of pixels, in latin typefaces
        # the 'x-height' area. Once the pixel density passes a threshold,
        # the 'x' area is found, once it drops below a threshold, it is
        # considered finished. Originally, both thresholds were 1,
        # but some lines have higher density areas before the 'x',
        # (e.g. Gn vts-035_2L.tif line 19), so now it is set to 2.
        # --- Correction: now it is 1,5, for 051_2L l23 and 064_1R l32 ---
        # --- were not split with too high threshold of 2 ---
        # That seems to work. Uncomment above line to see density values.
        if not foundx and not pastx and rd/td > 1.5:
            foundx = True
        elif foundx and not pastx and rd/td < 1:
            prevbounds = tuple(getboundaries(row, x1))
            pastx = True
        elif pastx:
            # now start tracking descenders.
            # as long as they are diminishing
            bounds = tuple(getboundaries(row, x1))
            new, connected = boundconnects(prevbounds, bounds)
            if not new and nextline: # reset if new pixel groups end
                line, nextline = tuple(), tuple()
                end = None
            elif new:
                if not end:     # mark the end of the non-overlapping line,
                    end = y     # now start tracking the overlap
                if connected:
                    line = mergeboundaries(line+connected)
                    nextline = mergeboundaries(nextline+new)
                else:
                    yield (start, end)
                    if verbose:
                        print ('start, end', start, end)
                    startoverlap = end # end of non-overlapping line is start
                    endoverlap = y
                    if verbose:
                        print(f'overlap: {startoverlap}-{endoverlap}, connects: {line}, next line: {nextline}')
                    # TODO do somethine with the overlaps which are now ignored
                    # reset all values for next line:
                    line, nextline = tuple(), tuple()
                    start, end = y, None
                    foundx, pastx, prevbounds = None, None, None
            prevbounds = connected
    if verbose:
        print ('start, end', start, y+1)
    yield (start, y+1)

def boundconnects(oldbounds, newbounds, dist=0):
    '''
    Compare pixelgroups in newbounds with those oldbounds.

    Return those boundaries that are connected to pixels in oldbounds,
    and those that are not connected (and thus 'new').

        0123456789
    b1    11 1          [(2,4),(5,6)]
    b2  1  1  1  1      [(0,1),(3,4),(6,7),(9,10)]
    '''
    # dist is maximum distance to be considered overlap
    # about overlap:
    # https://nedbatchelder.com/blog/201310/range_overlap_in_two_compares.html
    i = 0 # counter for bounds1
    new = []
    connected = []
    b1 = None
    for b2 in newbounds: # loop over bounds2, that is the only set we care about
        start2, end2 = b2
        while (b1 is None or end1+dist < start2) and i < len(oldbounds):
            b1 = oldbounds[i]   # skip over all b1 that end before start b2
            start1, end1 = b1
            i += 1
        if b1 is None or (end1+dist < start2 or end2+dist < start1):
            new.append(b2)
        else:
            connected.append(b2)
    return tuple(new), tuple(connected)

# def overlap(b1, b2, dist=1):
#     '''Checks if two ranges (almost) overlap, dist sets maximum distance'''
#     # https://stackoverflow.com/a/6821193
#     return bool(set(range(b1[0], b1[1]+dist)) & set(range(b2[0], b2[1]+dist)))
#     # or simpler:
#     # https://nedbatchelder.com/blog/201310/range_overlap_in_two_compares.html
#     # return b1[1]+dist >= b2[0] and b2[1]+dist >= b1[0]

def findmaincolumn(lines):
    b = tuple() # b: cumulative boundaries
    for line in lines:
        bounds = tuple((e[0], e[2]) for e in line.elements)
        b = mergeboundaries(b+bounds)
    # return the boundaries of the largest element in b
    return max(b, key=lambda e: e[1]-e[0])

def mergeboundaries(boundaries, min_gap=0):
    # if min_gap is set, combine boundaries of min_gap or less pixels apart
    result = []
    prevs, preve = None, None
    for s, e in sorted(boundaries):
        if not prevs and not preve:
            prevs, preve = s, e
        elif s > preve+min_gap: # if start exceeds previous end, add new bound
            result.append((prevs, preve))
            prevs, preve = s, e
        elif e > preve: # if end exceeds previous end, replace it
            preve = e
    result.append((prevs, preve)) # add last element when done

    return tuple(result)

# # Beautiful but unnecessary functions getmargins() and findgap()
# # getmargins() is replaced by findmaincolumn()
# def getmargins(im, margin_gap=None):
#     if margin_gap is None:
#         margin_gap = DEFAULT_MARGIN_GAP
#     min_gap = im.dpi[0] * margin_gap
#
#     x1, y1, x2, y2 = im.getbbox()
#     search_from = (x2 - x1) // 4
#
#     boxleft = (x1, y1, x1+search_from, y2)
#     lbound = findgap(im.cols(boxleft, reverse=True), min_gap)
#
#     boxright = (x2-search_from, y1, x2, y2)
#     rbound = findgap(im.cols(boxright), min_gap)
#
#     return lbound, rbound
#
# def findgap(cols, min_gap):
#     '''Returns the boundary of the first gap found in cols'''
#     boundary = None
#     for x, col in cols:
#         if isempty(col):
#             if not boundary:
#                 boundary = x
#             if boundary and abs(x-boundary) >= min_gap:
#                 break
#         else:
#             if boundary:
#                 boundary = None
#     return boundary



###############################################################################
# Line class and functions
###############################################################################

class Line:
    '''Line'''

    def __init__(self, lines, im, box, linetype=None):
        # x1, y1, x2, y2 = box

        self.num = len(lines)
        self.bbox = im.getbbox(box)
        self.elements = getelements(im, self.bbox)
        # self.elements = tuple(getboundaries(im.cols(self.bbox), self.bbox[0]))
        # self.xheight = getxheight(im, self.bbox)
        # self.baseline = getbaseline(im, self.bbox)
        self.baseline, self.xheight = getxheight(im, self.bbox)
        self.type = linetype
        if linetype is None:
            self.type = self.guesstype(lines, im.dpi)

        # self.linedist = 0 #self.baseline
        # if lines:
        #     self.linedist = self.baseline - lines[-1].baseline

    def __repr__(self):
        return '<Line {}: bbox: {}, type: {}, baseline {}, xheight: {}, height: {}>'.format(
            self.num,
            self.bbox,
            self.type,
            self.baseline,
            self.xheight,
            self.bbox[3]-self.bbox[1],
        )

    def guesstype(self, lines, dpi, no_header=False):

        if not lines:
            linetype = 'header'
        else:
            prevtype = lines[-1].type
            header_width = lines[0].bbox[2] - lines[0].bbox[0]
            center = lines[0].bbox[0] + (header_width//2)
            l = self.elements[0][0]
            r = self.elements[-1][2]
            height = self.bbox[3] - self.bbox[1]
            if header_width > 100:
                l_m = lines[0].elements[0][0]
                r_m = lines[0].elements[-1][2]
            else:
                l_m = center - 575 # distances from center of first page
                r_m = center + 565
            if prevtype == 'header' and not self.hascolumngap(center, gapwidth=100):
                linetype = 'title'
            elif height > 20 and l < center < r and (l > l_m + 50 or r < r_m - 50):
                linetype = 'app'
            else:
                linetype = 'text'
        return linetype


    def guesstype_(self, lines, dpi, no_header=False):

        # TODO : add option no_header, to set first line on
        # some pages to 'text' instead of 'header'
        elementwidths = [x2-x1 for x1,y1,x2,y2 in self.elements]
        # print(sum(elementwidths)//len(elementwidths))

        if lines:
            l_m, r_m = findmaincolumn(lines+[self])    # left, right margin
            w = r_m-l_m                         # width of main column
            l,r = self.bbox[0], self.bbox[2]
            prevtype = lines[-1].type if lines else None
            inch = int(dpi[0])                  # number of pixels per inch
            linedist = self.baseline - lines[-1].baseline
            linedist_text = inch*LINEDIST_TEXT
            linedist_app = inch*LINEDIST_APP
            offcenter = abs((l-l_m)-(r_m-r))    # deviation from center
            # linedistdif = self.linedist - lines[-1].linedist

        if not lines:               # first line is always 'header', unless
            linetype = 'header' if not no_header else 'text' # no_header is True
        elif prevtype == 'header':  # line after 'header' is always 'text'
            linetype = 'text'
        elif (l > (w-inch/2)/2+l_m and r < (w+inch/2)/2+l_m and # within centermost HALF inch
              offcenter < inch//5):                        # and centered
            linetype = 'pagenr'
        elif prevtype == 'pagenr' and l > r_m-inch:
            linetype = 'signaturemark'
        elif l < l_m or r > r_m:    # elements in margins only with text
            linetype = 'text'
        elif  l > l_m+(inch/4) and prevtype == 'text': # if right-aligned
            linetype = 'text'                            # or centered
        elif (r > r_m-(inch/10) and
              abs(linedist_text-linedist) < inch/75 and  # 4px@300dpi
              prevtype == 'text'):
            linetype = 'text'
        elif (abs(linedist_app-linedist) < inch/75 and  # 4px@300dpi
              prevtype in ('apparatus1', 'apparatus2')):
            linetype = prevtype
        elif (prevtype == 'text' and l < l_m+inch/5 #10
            and (sum(elementwidths)//len(elementwidths) > inch/20 or r < l + inch)):
        # elif (prevtype == 'text' and abs(linedist_text-linedist) > inch/75 and
        #       l > l_m+inch/10 and l < l_m+inch):
            linetype = 'apparatus1'
        elif (prevtype == 'text' and abs(linedist_text-linedist) > inch/75 and
              l < l_m+inch/10):
            linetype = 'mslist'
        elif prevtype == 'apparatus1' and abs(linedist_app-linedist)>inch/75:
            linetype = 'mslist'
        elif prevtype in ('mslist', 'apparatus2'):
            linetype = 'apparatus2'
        else:
            linetype = 'UNKNOWN'

        return linetype

    def hascolumngap(self, center, gapwidth=30):
        gap1, gap2 = center-(gapwidth//2), center+(gapwidth//2) #TODO: distance relative to dpi
        return all((gap2 < x1 or x2 < gap1) for x1,y1,x2,y2 in self.elements)


def getelements(im, box=None):

    if type(im) is not Im:
        im = Im(im) # wrap PIL image in Im wrapper class

    if box is None:
        box = (0, 0, im.width, im.height)

    x1, y1, x2, y2 = box
    boundaries = getboundaries(im.cols(box), x1)
    return tuple(im.getbbox((b[0],y1,b[1],y2)) for b in boundaries)

def getxheight(im, box=None, stoponfirstbaseline=False, verbose=False):

    if type(im) is not Im:
        im = Im(im) # wrap PIL image in Im wrapper class

    if box is None:
        box = (0, 0, im.width, im.height)

    td, rowdens = getdensity(im, box)

    xtop, baseline = None, None
    for y, rd in rowdens:
        # if box[3]-box[1]>80:
        #     print(rd/td)
        if rd/td > 1:
            if xtop is None:
                xtop = y
            baseline = y
        if stoponfirstbaseline and xtop and rd/td < 0.4:
            break

    if xtop is None and baseline is None:
        if verbose:
            print(f'No xheight found for line {box}. Used getbaseline() instead.')
        xtop = baseline = getbaseline(im, box)

    return (baseline, baseline-xtop)

def getdensity(im, box=None):

    if type(im) is not Im:
        im = Im(im) # wrap PIL image in Im wrapper class

    if box is None:
        box = (0, 0, im.width, im.height)

    x1, y1, x2, y2 = box
    w, h = x2-x1, y2-y1
    rowdens = []
    totpix = 0
    # first count pixels per row
    for y, row in enumerate(im.rows(box), y1):
        numpix = sum(bool(p) for p in row)
        totpix += numpix
        rd = numpix / w # rd: row density
        rowdens.append((y, rd))

    td = totpix / (w*h) # td: total density

    return (td, rowdens)

def getbaseline(im, box=None):
    '''Find the baseline by looking for the lowest line with most pixels'''

    if type(im) is not Im:
        im = Im(im) # wrap PIL image in Im wrapper class

    if box is None:
        box = (0, 0, im.width, im.height)

    # Works well, but to use bottom of xheight works maybe better.
    # Used as fallback function when nox xheight found
    x1, y1, x2, y2 = box
    max_pixels = 0
    baseline = None
    for y, row in enumerate(im.rows(box), y1):
        s = sum(bool(p) for p in row)
        if s >= max_pixels:
            max_pixels = s
            baseline = y
    return baseline

#------------------------------------------------------------------------------
# drawboxes functions to generate images with coloured line boxes
#------------------------------------------------------------------------------

def drawrect(drawcontext, xy, outline=None, width=0):
    """Draw a rectangle with option to set outline width"""
    # ImageDraw.rectangle() has no width option for some reason
    try:
        x1, y1, x2, y2 = xy
    except ValueError:
        (x1, y1), (x2, y2) = xy
    points = (x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)
    drawcontext.line(points, fill=outline, width=width)

def drawboxes(filename, lines):
    from PIL import Image, ImageDraw, ImageFont
    # define some colours
    # FOP = full opacity (255), HOP = half opacity (128), TRN = transparent
    BLACK_FOP = (0,0,0,255)
    WHITE_FOP = (255,255,255,255)
    WHITE_TRN = (255,255,255,0)
    RED_FOP = (255,0,0,255)
    RED_HOP = (255,0,0,128)
    GREEN_FOP = (0,255,0,255)
    GREEN_HOP = (0,255,0,128)
    # line widths
    BASELINE_WIDTH = 4
    SECTLINE_WIDTH = 4
    # define font
    FONT_FILE = 'Pillow/Tests/fonts/FreeMono.ttf'
    FONT_SIZE = 32
    BASELINE_ADJUST = 26
    # define sections
    SECTIONS = ('main', 'marginl', 'marginr')

    # open base image
    im = Image.open(filename).convert('RGBA')

    # make a blank image for the text, initialized to transparent text color
    txt = Image.new('RGBA', im.size, WHITE_TRN)

    # get a font
    fnt = ImageFont.truetype(FONT_FILE, FONT_SIZE, 0)
    # get a drawing context
    d = ImageDraw.Draw(txt)

    # draw filename at top of image
    d.text((10,10), filename, font=fnt, fill=BLACK_FOP)
    for line in lines:
        # draw baseline
        points = [(0, line['baseline']), (im.width, line['baseline'])]
        d.line(points, fill=GREEN_HOP, width=BASELINE_WIDTH)
        for section in SECTIONS:
            # draw sections
            if line[section] is None:
                continue
            drawrect(d, line[section], outline=RED_HOP, width=SECTLINE_WIDTH)
        # draw line tag
        tag = f"{line['num']} {line['type']}: {line['baseline']}"
        t_offset = 10, line['baseline'] - BASELINE_ADJUST
        d.text(t_offset, tag, font=fnt, fill=BLACK_FOP)

    return Image.alpha_composite(im, txt)
