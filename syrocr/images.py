from PIL import Image, ImageOps, ImageChops

# TODO make consistent use of constants, or not at all
DEFAULT_DPI = (300.0, 300.0)
DEFAULT_MARGIN_GAP = 1/30 # 1/30 inch (10px@300dpi).
HALFMM = 1/50 # 0.508 mm


###############################################################################
# Im class and functions
###############################################################################


class Im:
    '''Wrapper class for PIL.Image'''
    # Unfortunately Image.Image cannot be subclassed, so used wrapper
    # with __getattr__() (see https://stackoverflow.com/a/5165352)

    def __init__(self, image='./vts-030_2L.tif', dpi=None):
        # Open, convert to RGB (required for invert), and invert image
        # Invert is necessary for getbbox, which cuts off black borders
        if type(image) is str:
            self.image = ImageOps.invert(Image.open(image).convert('L'))
        else:
            self.image = image
        # save pixel data in a tuple
        self.data = tuple(self.image.getdata())
        # save pixel data for transposed image in another tuple
        self.data_tr = tuple(self.image.transpose(Image.TRANSPOSE).getdata())
        # set width, height, dpi
        # self.width = self.image.width
        # self.height = self.image.height
        self.dpi = getdpi(self.image, dpi)

    def __getattr__(self, key):
        # delegate unimplemented attributes/methods to self.image:
        # https://stackoverflow.com/a/5165352
        if key == 'image':
            #  http://nedbatchelder.com/blog/201010/surprising_getattr_recursion.html
            raise AttributeError()
        return getattr(self.image, key)

    def getbbox(self, box=None):
        if box is None:
            bbox = self.image.getbbox()
        else:
            relbbox = self.image.crop(box).getbbox()
            offset = box[:2] + box[:2] # set left top as offset for both points
            bbox = tuple(a+b for a, b in zip(offset, relbbox))
        return bbox

    def rows(self, box=None, reverse=False):
        '''Returns generator with rows of pixels'''
        if box is None:
            box = (0, 0, self.width, self.height)
        return getrows(self.data, self.width, box, reverse)

    def cols(self, box=None, reverse=False):
        '''Returns generator with rows of pixels of transposed image'''
        if box is None:
            box = (0, 0, self.height, self.width)
        else:
            box = box[1], box[0], box[3], box[2] #transpose coordinates
        return getrows(self.data_tr, self.height, box, reverse)


def getrows(data, width, box, reverse=False):
    x1, y1, x2, y2 = box
    rows = range(y1, y2)
    if reverse:
        rows = reversed(rows)
    for y in rows:
        yield data[y*width+x1:y*width+x2]

def getdpi(image, dpi):
    if dpi is None:
        if 'dpi' in image.info:
            dpi = image.info['dpi']
        else: # default
            dpi = DEFAULT_DPI
    return dpi


###############################################################################
# BoundIm class and functions
###############################################################################

class BoundIm:
    '''Image consisting of column boundaries, with height, offset and baseline'''

    # TODO to serialize images to json in base64:
    # https://stackoverflow.com/a/31826470
    # see also: https://docs.python.org/3/library/io.html#binary-i-o

    def __init__(self, height, offset=(0, 0), boundaries=None, baseline=None):
        # note to self DO NOT pass an empty list as default argument!
        # http://docs.python-guide.org/en/latest/writing/gotchas/#mutable-default-arguments
        self.boundaries = boundaries if boundaries is not None else [[]]
        self.width = len(self.boundaries)
        self.height = height
        self.offset = offset
        self.baseline = baseline

    def __repr__(self):
        return f'<BoundIm offset {self.offset} len {len(self.boundaries)}>'

    def addcolumn(self):
        self.boundaries.append([]) # add empty column, to add boundaries to
        self.width = len(self.boundaries)

    def addboundary(self, boundary):
        self.boundaries[-1].append(boundary)

    def image(self):
        # height and width substituted since image is transposed:
        im = Image.new('L', (self.height, self.width))
        im.putdata(pxfrombounds(self.boundaries, self.height))
        return Im(im.transpose(Image.TRANSPOSE))

    def cropped(self):
        return cropped(self)

    def slice(self, start, end):
        offset = self.offset[0] + start, self.offset[1]
        boundaries = self.boundaries[start:end]
        return BoundIm(self.height, offset, boundaries, self.baseline)

    def combine(self, boundim2):
        '''Combines self and boundim2 and returns as new BoundIm'''
        return combineboundims(self, boundim2)

    def strip_connecting_line(self):
        return strip_connecting_line(self)

def strip_connecting_line(boundim):
    start = 0
    end = boundim.width - 1
    while ( start < boundim.width - 1
            and (not boundim.boundaries[start]
            or isconnectingline((boundim.boundaries[start][0][0], boundim.boundaries[start][-1][1]), boundim.baseline))
    ):
        start += 1
    while ( end > 1 and
           (not boundim.boundaries[end]
            or isconnectingline((boundim.boundaries[end][0][0], boundim.boundaries[end][-1][1]), boundim.baseline))
    ):
        end -= 1
    if start >= end:
        return boundim
    else:
        return boundim.slice(start, end)

def isconnectingline(bound, baseline, maxheight=6, maxdeviation=4):
    start, end = bound
    return (end - start < maxheight and # if not too high
            end < baseline + maxdeviation and
            start > baseline - maxdeviation - maxheight)

def cropped(boundim):
    top = min(b[0] for col in boundim.boundaries for b in col)
    bot = max(b[1] for col in boundim.boundaries for b in col)
    boundaries = [[(b[0] - top, b[1] - top) for b in col] for col in boundim.boundaries]
    height = bot - top
    offset = (boundim.offset[0], boundim.offset[1] + top)
    baseline = boundim.baseline - top if boundim.baseline is not None else None
    return BoundIm(height, offset, boundaries, baseline)

def pxfrombounds(bounds, height, offvalue=0, onvalue=255):
    '''transform 'boundary' data into a list of pixel data'''
    pxdata = []
    for bcol in bounds:
        pos = 0
        pcol = []
        for start, end in bcol:
            for p in range(pos, start):
                pcol.append(offvalue)
            for p in range(start, end):
                pcol.append(onvalue)
            pos = end
        for p in range(len(pcol), height):
            pcol.append(offvalue)
        pxdata.extend(pcol)
    return pxdata

def combineboundims(boundim1, boundim2):
    offsetx = min(boundim1.offset[0], boundim2.offset[0])
    offsety = min(boundim1.offset[1], boundim2.offset[1])
    width = max(im.offset[0] + im.width for im in (boundim1, boundim2)) - offsetx
    height = max(im.offset[1] + im.height for im in (boundim1, boundim2)) - offsety
    if None in (boundim1.baseline, boundim2.baseline):
        baseline = None
    else:
        baseline = max(boundim1.baseline, boundim2.baseline)
    boundaries = [[] for i in range(width)]
    for im in (boundim1, boundim2):
        hshift = im.offset[0] - offsetx
        vshift = im.offset[1] - offsety
        for i, bounds in enumerate(im.boundaries, start=hshift):
            shiftedbounds = [(b[0] + vshift, b[1] + vshift) for b in bounds]
            boundaries[i] = sorted(boundaries[i] + shiftedbounds)
    return BoundIm(height, (offsetx, offsety), boundaries, baseline)

# def combinechars(c1, c2):
#     '''Combine two connecting Char objects into one'''
#     # sort chars so that c2 has the most columns
#     c1, c2 = sorted((c1, c2), key=lambda x: len(x.boundaries))
#     # c2 being the biggest character will be returned, with boundaries of c1 added
#     d = len(c2.boundaries) - len(c1.boundaries)
#     for i in range(len(c1.boundaries)):
#         c2.boundaries[i+d] = sorted(c1.boundaries[i] + c2.boundaries[i+d])
#     return c2

# def combineboundims1(boundim1, boundim2):
#     '''Combine two connecting Char objects into one'''
#     # sort chars so that i1 has lowest vertical offset
#     i1, i2 = sorted((boundim1, boundim2), key=lambda x: x.offset[1])
#     d = i2.offset[1] - i1.offset[1]
#     # shift the boundaries of i2 to start from the same vertical offset as i1
#     i2.boundaries = [[(b[0] + d, b[1] + d) for b in col] for col in i2.boundaries]
#     i2.offset = (i2.offset[0], i2.offset[1] - d)
#     i2.height = i2.height + d
#     # sort chars so that i1 has lowest horizontal offset
#     i1, i2 = sorted((i1, i2), key=lambda x: x.offset[0])
#     d = i2.offset[0] - i1.offset[0]
#     # add empty boundary columns to i1 to match the end of i2
#     if len(i1.boundaries) < d + len(i2.boundaries):
#         i1.boundaries += [[] for i in range(d + len(i2.boundaries) - len(i1.boundaries))]
#     # merge boundaries for i1 and i2 where they overlap to i1
#     for i in range(d, d + len(i2.boundaries)):
#         i1.boundaries[i] = sorted(i1.boundaries[i] + i2.boundaries[i-d])
#     # reset width and height, although unnecessary because of crop() right after?
#     # width is number of columns in i1.boundaries
#     i1.width = len(i1.boundaries)
#     # height is the value of the highest boundary in i1
#     # or the current height value if that is higher
#     i1.height = max(i1.height, max(b[1] for col in i1.boundaries for b in col))
# #     i1.crop()
#     return i1


###############################################################################
# AvgIm class and sorting functions
###############################################################################

class AvgIm:

    def __init__(self, firstim, baseline, width=None, height=None):
        if type(firstim) is not str:
            self.bw_im = firstim
            self.bw_offset = (0, 0)
            self.avgim = tobinary(firstim)
            self.minwidth = firstim.width
            self.maxwidth = firstim.width
            self.minheight = firstim.height
            self.maxheight = firstim.height
            self.minbaseline = baseline
            self.maxbaseline = baseline
        else:
            self.minwidth, self.maxwidth = width
            self.minheight, self.maxheight = height
            self.minbaseline, self.maxbaseline = baseline
            self.avgim = base64_to_im(firstim)
            # update bw_image and bw_offset
            bw_im = self.blackwhite()
            bw_bbox = bw_im.getbbox()
            self.bw_im = bw_im.crop(bw_bbox)
            self.bw_offset = tuple(bw_bbox[:2])


    def export(self):
        return {
            'width': (self.minwidth, self.maxwidth),
            'height': (self.minheight, self.maxheight),
            'baseline': (self.minbaseline, self.maxbaseline),
            'base64_str': im_to_base64(self.avgim),
        }

    def blackwhite(self):
        return blackwhite(self.avgim)

    def maxtoblack(self, invert=False):
        if invert:
            return ImageChops.invert(maxtoblack(self.avgim))
        else:
            return maxtoblack(self.avgim)

    def compare(self, im, baseline, deviation=2, maxerror=1, absmax=8):
        # deviation is the maximum amount any of width, height, baseline may be
        #           higher resp. lower than the known maximum or minimum values.
        # maxerror is the maximum error in percentage of the comparison between
        #          images. If maxerror is 1, then an image of 100 pixels may
        #          contain no more than 1 unmatched pixels after comparison.
        # absmax is the maximum absolute number of unmatched pixels, in order
        #        to prevent larger images to allow for e.g. diacritical dots
        if (self.minwidth - deviation <= im.width <= self.maxwidth + deviation and
            self.minheight - deviation <= im.height <= self.maxheight + deviation and
            self.minbaseline - deviation <= baseline <= self.maxbaseline + deviation):
            # how to round up a division:
            # https://bytes.com/topic/python/answers/658718-integer-division#post2615925
            size = min(im.width*im.height, 800)
            maxdens = -(-(im.width*im.height) // (maxerror*100))
            # correct maxdens with absmax if it is too large:
            maxdens = min(maxdens, absmax)
            dens, offset = compare(self.bw_im, im)
            if dens <= maxdens:
                return offset
            else:
                return False
        else:
            return False

    def add(self, im, baseline, offset):
        # boring administration ## TODO why not use min()/max()?
        if im.width < self.minwidth:
            self.minwidth = im.width
        if im.width > self.maxwidth:
            self.maxwidth = im.width
        if im.height < self.minheight:
            self.minheight = im.height
        if im.height > self.maxheight:
            self.maxheight = im.height
        if baseline < self.minbaseline:
            self.minbaseline = baseline
        if baseline > self.maxbaseline:
            self.maxbaseline = baseline

        # offset is the offset compared with the bw_im.
        # Since that may be smaller than the avgim,
        # correct the difference
        offset = (
            offset[0] + self.bw_offset[0],
            offset[1] + self.bw_offset[1]
        )
        # first expand avgim to match the add im if necessary
        avgbox = (
            min(0, offset[0]),
            min(0, offset[1]),
            max(im.width+offset[0], self.avgim.width),
            max(im.height+offset[0], self.avgim.height),
        )
        imbox = (
            min(0, -offset[0]),
            min(0, -offset[1]),
            max(self.avgim.width-offset[0], im.width),
            max(self.avgim.height-offset[1], im.height),
        )
        # add new data to avgim
        self.avgim = add(self.avgim.crop(avgbox), im.crop(imbox))
        # update bw_image and bw_offset
        bw_im = self.blackwhite()
        bw_bbox = bw_im.getbbox()
        self.bw_im = bw_im.crop(bw_bbox)
        self.bw_offset = tuple(bw_bbox[:2])


def base64_to_im(base64string):
    # https://stackoverflow.com/a/26079673
    import io, base64
    return Image.open(io.BytesIO(base64.b64decode(base64string)))

def im_to_base64(im):
    '''Export PIL image to base64 string'''
    # https://stackoverflow.com/a/42505258
    import io, base64
    in_mem_file = io.BytesIO()
    im.save(in_mem_file, format = "PNG")
    # reset file pointer to start
    in_mem_file.seek(0)
    img_bytes = in_mem_file.read()
    base64_encoded_result_bytes = base64.b64encode(img_bytes)
    return base64_encoded_result_bytes.decode('ascii')

def maxtoblack(im):
    """Give the average image with max value scaled to 255"""
    maxval = im.getextrema()[1]
    return Image.eval(im, lambda x: int(x/maxval * 255))

def blackwhite(im):
    """Give B/W image with every pixel that is true in half or more cases set to max (=white)"""
    maxval = im.getextrema()[1]
    return Image.eval(im, lambda x: 255 if x >= maxval/2 else 0)

def tobinary(im):
    """Returns the image with all non-zero pixels set to one"""
    return Image.eval(im, lambda x: 1 if bool(x) else 0)

def add(avgim, im):
    """Add pixel data of im to the values of avgim, if it does not exceed the maximum of 255"""
    if avgim.getextrema()[1] < 255:
        avgim = ImageChops.add(avgim, tobinary(im))
    return avgim

def dens(im):
    return sum(bool(c) for c in im.getdata())

def expandimg(im, dim):
    if type(dim) is int:
        l = t = r = b = dim
    elif len(dim) == 1:
        l = t = r = b = dim[0]
    elif len(dim) == 2:
        l, t = r, b = dim
    elif len(dim) == 4:
        l, t, r, b = dim
    else:
        raise ValueError
    box = (-l,-t,im.size[0]+r,im.size[1]+b)
    return im.crop(box)

def compare(refim, im, shift=1):
    '''
    Compare two images.

    Get the difference between two images. Finds the smallest
    possible difference by shifting the positions of the images
    relative to each other when they differ in size, and
    add pixels to the largest of the images to shift even more.
    When the smallest possible difference is found, the edges
    are removed with removeedges, so that almost identical images
    should evaluate as identical.
    Return: image with difference between two images
    '''
    # The o_w and o_h values register the relative offset of the widest
    # resp. highest of the images to the other one, so in order to
    # calculate the correct relative offset for im in relation to refim
    # (the reference image), we must first register the 'sign',
    # i.e. whether the movement is positive or negative, for both
    # directions.
    w_sign = -1 if im.width < refim.width else 1
    h_sign = -1 if im.height < refim.height else 1

    lowdens = None
    lowdiff = None
    # first sort the two images by width
    imw1, imw2 = sorted((refim, im), key=lambda x: x.width)
    # expand the widest image to both sides, for more shifting options
    imw2 = expandimg(imw2, (shift, 0))
    dif_w = (imw2.width - imw1.width)
    for o_w in range(dif_w+1):
        #box = (o_w, 0, imw1.size[0] + o_w, imw2.size[1])
        #imh1, imh2 = sorted((imw1, imw2.crop(box)), key=lambda x: x.size[1])
        # edit: instead of shrinking the wider image to fit, expand the narrow one
        box = (-o_w, 0, imw2.width-o_w, imw1.height)
        imh1, imh2 = sorted((imw1.crop(box), imw2), key=lambda x: x.height)
        # expand the highest image
        imh2 = expandimg(imh2, (0, shift))
        dif_h = imh2.height - imh1.height
        for o_h in range(dif_h+1):
            #box = (0, o_h, imh1.size[0], imh1.size[1] + o_h)
            #crop1, crop2 = imh1, imh2.crop(box)
            # edit: instead of shrinking the higher image to fit, expand the lower one
            box = (0, -o_h, imh1.width, imh2.height-o_h)
            crop1, crop2 = imh1.crop(box), imh2
            diff = ImageChops.difference(crop1, crop2)
            difdens = dens(diff)
            if lowdens is None or lowdens > difdens:
                lowdens = difdens
                lowdiff = (diff, crop1, crop2)
                # calculate relative offset, correcting for the shift value
                offset = ((w_sign*shift - w_sign*o_w), (h_sign*shift - h_sign*o_h))
#             print(difdens)
#     diff = removeedges(*lowdiff)
    # return dens(diff), diff
#     return lowdiff
    return dens(removeedges(*lowdiff)), offset

def removeedges(diffim, orim1, orim2):
    '''Remove edge difference'''
    im=diffim.copy() # do not change original (TODO actually, why not?)
    for x in range(im.size[0]):
        for y in range(im.size[1]):
            if im.getpixel((x,y)):
                # select image in which this pixel is 0
                checkedge = orim2 if orim1.getpixel((x,y)) else orim1
                # from that image, take the surrounding pixels
                area = checkedge.crop((x-1,y-1,x+2,y+2))
                # count the non-black pixels
                neighbours = dens(area)
                # if there are any, remove the current pixel
                if neighbours:
                    im.putpixel((x,y),0)
    return im

def addtochartable(table, char):
    # table is a list of dicts: {'id': c_id, 'avgim': avgim, 'key': key}
    if char.width >= 10:
        char = char.strip_connecting_line()
    found = False
    for c in table:
        offset = c['avgim'].compare(char.image(), char.baseline)
        if offset:
            c['avgim'].add(char.image(), char.baseline, offset)
            found = True
            break
    if not found:
        c = {'id': len(table),
             'avgim': AvgIm(char.image(), char.baseline),
             'key': None,
            }
        table.append(c)
    return c

def imgtable(table, spacing=2, maxwidth=5000):
    im = Image.new('L',(0,0))
    y=0
    for c_id, avgim, c_list in table:
        x=0
        # w=sum(e.size[0] for e in row) + (len(row)-1)*spacing
        # h=max(e.size[1] for e in row)
        w = avgim.avgim.width + sum(c.width+spacing for c in c_list)
        h = avgim.avgim.height
        im = im.crop((0, 0, max(im.width, w), im.height+h+spacing))
        im.paste(avgim.maxtoblack(), (x, y))
        x += avgim.avgim.width+spacing
        for c in c_list:
            im.paste(c.image(), (x,y))
            x += c.width+spacing
            if x > maxwidth:
                break
        y += h+spacing
    return ImageChops.invert(im)
