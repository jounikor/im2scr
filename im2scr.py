#!/usr/bin/python

import argparse
from PIL import Image

#
# (c) 2016 Jouni Korhonen
#
# Convert pictures suitable for ZX Spectrum screen format
#
#
#


class ZXException(BaseException):
    '''The ZXException class is a base exception class for all zx object
    specific exceptions. This class does not currently implement any own
    methods.
    '''
    pass


#
#
class zx(object):
    '''
    The zx class implements a set of methods and functions to convert any
    picture format supported by PIL into ZX Spectrum native screen
    resolution frame buffer format. The zx class also attempts the
    possible palette/color conversions. However, the color conversion
    algorithm is naive to begin with.

    The zx class also supports cropping the original picture and saving the
    pictures either with a linear buffer or using ZX Spectrum frame buffer
    layout. When using ZX Spectrum frame buffer layout the height of the
    (cropped) picture must in multiple of 64 pixels, otherwise an exception
    gets thrown.
    '''
    BLACKTRESH = 100
    BRIGHT0 = 0xd7
    BRIGHT1 = 0xff
    DEFX = 0
    DEFY = 0
    MAXW = 256
    MAXH = 192
    BLACKWEIGHT = 255
    PREFERBRIGHT = None

    def __init__(self, im, prefer=None):
        '''
        x.__init__(self, im) Initializes x.

        :param im: a PIL.Image object, which must be either in palette,
            greyscale or black and white format.
        :param prefer: a boolean guiding the color conversion to either
            prefer BRIGHT colors or dimmer colors in a case of conflict.
        '''
        # Do sanity checks for the im object
        if im.mode not in ("P", "L", "1"):
            raise ValueError("Image object in a wrong format")

        # default buffers for ZX Spectrum pictures..
        self._scr = bytearray(32 * 192)
        self._attr = bytearray(32 * 24)
        self._scrSize = 0
        self._attrSize = 0
        self._mid = 0
        self._hgh = 0
        self._linear = False             # save linear or zx screen buffer
        self._w = 0
        self._h = 0
        self._modulo = 0
        self._preferbright = prefer

        #
        if im.size[0] > self.MAXW:
            raise ValueError("Image width greater than {0}".format(self.MAXW))
        if im.size[1] > self.MAXH:
            raise ValueError("Image height greater than {0}".format(self.MAXH))

        self.im2scr(im)
        self.modulo = (self.MAXW >> 3) - self._w

    @classmethod
    def open(cls, name, **kwargs):
        '''
        x.open(...) -> zx object

        Opens "any" format picture from a file and prepares that for further
        processing. This classmethod also allows cropping the the source
        picture into a desired size. The default is 256x192.

        :param cls: the class object.
        :param name: the filename of the source picture.
        :param **kwargs: list of parameters describing the size of the final
            picture.

        The kwargs parameters are:

        :param x: the left corner x, defaults to zx.DEFX.
        :param y: the left corner y, defaults to zx.DEFY.
        :param w: the width of the picture, defaults to zx.MAXW.
        :param h: the height of the picture, defaults to zx.MAXW.
        :param prefer: a boolean for preferring BRIGHT colors.

        :return zx object: the cropped picture ready for further
            processing.
        '''
        # the default picture crop size..
        x = zx.DEFX
        y = zx.DEFY
        w = zx.MAXW
        h = zx.MAXH
        prefer = zx.PREFERBRIGHT

        # now.. check if we need to update the picture crop size..
        if kwargs:
            if 'xpos' in kwargs:
                x = kwargs['xpos']
            if 'ypos' in kwargs:
                y = kwargs['ypos']
            if 'width' in kwargs:
                w = kwargs['width']
            if 'height' in kwargs:
                h = kwargs['height']
            if 'prefer' in kwargs:
                prefer = kwargs['prefer']

        # Check crop size..
        if w > zx.MAXW:
            raise ValueError("Crop width greater than {}}".format(zx.MAXW))

        if h > zx.MAXH:
            raise ValueError("Crop height greater than {}}".format(zx.MAXH))

        # load the victim picture..
        im = Image.open(name)

        # Sanity checks..
        if x + w > im.size[0]:
            raise ValueError("Crop width bigger than picture width")
        if y + h > im.size[1]:
            raise ValueError("Crop height bigger than picture height")

        return zx(zx.crop(im, (x, y, w, h)), prefer)

    #
    #
    @classmethod
    def crop(cls, im, (x, y, w, h)):
        '''
        x.xrop(...) -> PIL.Image
        '''
        box = (x, y, x + w, y + h)

        # Check picture size related to attributes
        if (x + w) % 8 != 0:
            print "**Warning: picture crop x size not divisible by 8"

        if (y + h) % 8 != 0:
            print "**Warning: picture crop y size not divisible by 8"

        # Crop the picture as desired..
        tmp = im.crop(box)

        # Convert victing to palette mode picture if it is not already..
        if tmp.mode not in ("P", "L", "1"):
            try:
                tmp = tmp.convert("P", dither=Image.NONE, palette=Image.ADAPTIVE, colors=16)
            except Exception as e:
                raise ZXException("Conversion failed: {}".format(e))

        return tmp

    # convert linear y position to ZX Spectrum y position
    @staticmethod
    def y2zx(y):
        hh = y & 0b00111000
        hl = y & 0b00000111
        return y & 0xc0 | hh >> 3 | hl << 3

    # R G B
    # 4 2 1

    _palette = [0x00, 0x01, 0x04, 0x05, 0x02, 0x03, 0x06, 0x07]
    _rgb = [(0, 0, 0), (0, 0, 215), (215, 0, 0), (215, 0, 215),
            (0, 215, 0), (0, 215, 215), (215, 215, 0), (215, 215, 215),
            (0, 0, 0), (0, 0, 255), (255, 0, 0), (255, 0, 255),
            (0, 255, 0), (0, 255, 255), (255, 255, 0), (255, 255, 255)]

    #

    def verifyrgb(self, r, g, b):
        """ Convert RGB values into ZX Spectrum palette RGB values.
        Also check whether colors have BRIGHT set.

        r is R component
        g is G component
        b is B component

        Return converted RGB values.
        """
        c = 0
        cb = 0

        if r >= zx.BLACKTRESH:
            if abs(r - self._mid) < abs(r - self._hgh):
                c = 4
            else:
                cb = 4

        if g >= zx.BLACKTRESH:
            if abs(g - self._mid) < abs(g - self._hgh):
                c |= 2
            else:
                cb |= 2

        if b >= zx.BLACKTRESH:
            if abs(b - self._mid) < abs(b - self._hgh):
                c |= 1
            else:
                cb |= 1

        # Check if we have palette conversion BRIGH conflicts..
        if c > 0 and cb > 0:
            if self._preferbright is True:
                cb |= c
                c = 0
            elif self._preferbright is False:
                c |= cb
                cb = 0
            else:
                raise ZXException("Palette conversion not successful")

        if c == 0 and cb == 0:
            return zx._palette[0]

        if c:
            return zx._palette[c]
        else:
            return zx._palette[cb] | 0x40

    #
    #
    #
    def pal2attr(self, pal, num):
        """
        x.pal2attr(...) -> array

        Convert a palette of R,G,B entries to ZX Spectrum palette. Since
        most palettes are approximations, this method tries to figure out
        which colors are BRIGHT.

        :param pal: is the palette in a form of an array of R,G,B values.
        :param num: is the number of valid entries at the beginning of the
            palette.

        :return array: a conversion table from a picture pixel (an index to
            table of RGB values) to ZX Spectrum attribute values.
        """

        outp = []
        i = 0
        self._hgh = 0

        # find largest color component and use that for calculating
        # non-BRIGHT colors..

        while i < num*3:
            if pal[i] > self._hgh:
                self._hgh = pal[i]

            i += 1

        # prepare palette
        i = 0
        self._mid = 0.85 * self._hgh

        while i < num:
            r = pal[i*3+0]
            g = pal[i*3+1]
            b = pal[i*3+2]
            outp.append(self.verifyrgb(r, g, b))
            i += 1

        #
        return outp

    #
    def selectcolors(self, buf, stax, stay, w, h):
        '''
        x.seleccolors(...)

        Scan the source image and select appropriate colors from each 8x8
        block (or possibly something smaller at the edges) of the source
        picture. As part of the color selection the source picture is also
        scanned for errorneous number of colors. The method implements a
        dummy algorithm to deal with pictues that have, for some reason,
        more than 2 colors in their 8x8 block. This is typically due
        aliasing and stuff non-Spectrum tools or screen captures from Web
        cause. The precondition for this method to work that palette index
        0 has RGB componens (0,0,0). See method x.swappaper0() for this
        purpose.

        :param buf: an Image pixel access object to the source picture that
            can be used to read and modify pixels.
        :param stax: left corner x position in the picture.
        :param stay: left corner y position in the pciture.
        :param w: width of the block (less of equal to 8).
        :param h: height of the block (less or equal to 8).

        :return paper, ink: a tuple of indexes to ZX Spectrum palette for
            both PAPER and INK colors.
        '''

        c = {}
        y = stay

        while y < (stay + h):
            x = stax
            while x < (stax + w):
                pixel = buf[x, y]

                if pixel in c:
                    c[pixel] = c[pixel] + 1
                else:
                    c[pixel] = 1
                x += 1
            y += 1

        #
        paper0 = c.pop(0, None)
        colors = sorted(c, key=c.get, reverse=True)

        if len(colors) == 0:
            return 0, 0
        if paper0 is None:
            if len(colors) == 1:
                return colors[0], colors[0]
            else:
                return colors[0], colors[1]
        else:
            return 0, colors[0]

        # elif len(colors) == 1:
        #    if paper0 is None:
        #        return colors[0], colors[0]
        #    else:
        #        return 0, colors[0]
        # else:
        #    if paper0 is None:
        #        return colors[0], colors[1]
        #    else:
        #        return 0, colors[0]

    #
    def swappaper0(self, buf, size, pal, paper0):
        for y in xrange(size[1]):
            for x in xrange(size[0]):
                pixel = buf[x, y]

                if pixel == paper0:
                    buf[x, y] = 0
                elif pixel == 0:
                    buf[x, y] = paper0

        tmp = pal[0]
        pal[0] = pal[paper0]
        pal[paper0] = tmp

    # Convert the victim image to ZX spectrum format and also check possible
    # issues with number of colors in the image.
    def im2scr(self, im):
        '''
        x.im2scr(...)

        :param im: An PIL.Image object.
        :return ??:
        '''
        pal = im.getpalette()
        hist = im.histogram()

        numcolors = len(hist)

        if numcolors - hist.count(0) > 16:
            raise ZXException("Picture uses more than 16 colors")

        # convert RGB to ZX Spectrum palette colors
        apal = self.pal2attr(pal, numcolors)

        # Get the pixel buffer.
        buf = im.load()

        # If PAPER0 is not 'no pixel' modify the picture accordingly
        paper0 = apal.index(0)

        if paper0 != 0:
            self.swappaper0(buf, im.size, apal, paper0)
            paper0 = 0

        # Clear temporary color information..
        tmp = {}
        y = 0

        # Create color attributes for the converter picture.
        while y < im.size[1]:
            h = 8 if y + 8 < im.size[1] else im.size[1] - y
            x = 0

            while x < im.size[0]:
                w = 8 if x + 8 < im.size[0] else im.size[0] - x
                tmp[x >> 3, y >> 3] = self.selectcolors(buf, x, y, w, h)
                x += 8
            #
            y += 8

        #
        index = 0

        for y in xrange(im.size[1]):
            gfx = 1

            for x in xrange(im.size[0]):
                gfx = gfx << 1

                # Pixel with index 0 is treated specially.
                # It is considered as PAPER 0, which sets
                # no pixel in the target bitmap.
                pixel = buf[x, y]

                if pixel and pixel != tmp[x >> 3, y >> 3][0]:
                    gfx += 1

                # with x loop
                if gfx & 0x100:
                    self._scr[index] = (gfx & 0xff)
                    gfx = 1
                    index += 1

            # within y loop
            if gfx > 1:
                while not gfx & 0x100:
                    gfx = gfx << 1

                self._scr[index] = (gfx & 0xff)
                index += 1

        # Picture bitmap size
        self._scrSize = index

        # Final picture size.. (x in octet, y in pixels)
        x += 1
        y += 1
        self._w = int(x >> 3 if x % 8 == 0 else (x >> 3) + 1)
        self._h = int(y)

        #
        index = 0
        y8 = self._h
        y8 = y8 >> 3 if not y8 % 8 else (y8 >> 3) + 1

        for y in xrange(y8):
            for x in xrange(self._w):
                paper = apal[tmp[x, y][0]]
                ink = apal[tmp[x, y][1]]

                if paper and ink:
                    if (paper ^ ink) & 0x40:
                        if self._preferbright is True:
                            ink |= 0x40
                        elif self._preferbright is False:
                            ink &= ~0x40
                        else:
                            raise ZXException("Color attribute has BRIGHT conflict")

                self._attr[index] = (ink | (paper << 3)) & 0xff
                index += 1

        self._attrSize = index

        #
        return buffer(self._scr), buffer(self._attr)

    #
    #
    def getAttr(self):
        return buffer(self._attr, 0, self._attrSize)

    #
    def getScr(self):
        return buffer(self._scr, 0, self._scrSize)

    #
    def getScrSize(self):
        return self._scrSize

    #
    def getAttrSize(self):
        return self._attrSize

    def saveZX(self, name, attrs=True, linear=False):
        with open(name, "w") as f:
            if linear:
                f.write(buffer(self._scr, 0, self._scrSize))
            else:
                if self._h % 64 != 0:
                    raise ZXException("Cannot save an image because height is not mod 64")
                y = 0
                while y < self._h:
                    y2 = zx.y2zx(y)
                    f.write(buffer(self._scr, y2 * self._w, self._w))
                    y += 1

            if attrs:
                f.write(buffer(self._attr, 0, self._attrSize))

    #
    #
    #
    def showZX(self, color=False):
        '''
        x.openZX(...)

        Shows either a black & white or color preview of the converted
        picture.

        :param color: if True show color image, if Flase show just bitmap
            (black & whote).

        :returns nothing:
        '''

        if not color:
            b = buffer(self._scr)
            im = Image.frombuffer("1", (self._w << 3, self._h), b, "raw", "1", 0, 1)
        else:
            # Get a copy of the frame buffer

            im = Image.new("RGB", (self._w << 3, self._h))
            # im.putpalette(self._rgb)
            px, py = 0, 0
            x, y = 0, 0

            while y < self._h:
                while x < self._w:
                    b = self._scr[y * self._w + x]
                    c = self._attr[(y >> 3) * self._w + x]
                    inkIndex = (c & 0x07) | (0x8 if c & 0x40 else 0x00)
                    paperIndex = c >> 3

                    # This is slow.. but with this few pixels we do not care.
                    for n in xrange(8):
                        if b & 0x80:
                            im.putpixel((px, py), self._rgb[inkIndex])
                            # im[px, py] = self._rgb[inkIndex]
                        else:
                            im.putpixel((px, py), self._rgb[paperIndex])
                            # im[px, py] = self._rgb[paperIndex]
                        px += 1
                        b <<= 1
                    x += 1
                x = 0
                y += 1
                px = 0
                py += 1

        #
        im.show()

#
#
#


if __name__ == "__main__":

    # command line options..
    op = argparse.ArgumentParser()
    group1 = op.add_mutually_exclusive_group()
    group2 = op.add_mutually_exclusive_group()
    op.add_argument("-l", "--linear", dest="linear", help="save linear screen buffer",
                    action="store_true", default=False)
    op.add_argument("-x", "--xpos", dest="xpos", help="x position for cropping",
                    action="store", type=int, default=0)
    op.add_argument("-y", "--ypos", dest="ypos", help="y position for cropping",
                    action="store", type=int, default=0)
    op.add_argument("-X", "--width", dest="width", help="crop area width",
                    action="store", type=int, default=256)
    op.add_argument("-Y", "--height", dest="height", help="crop area height",
                    action="store", type=int, default=192)
    op.add_argument("input", help="input file to convert")
    op.add_argument("-o", "--output", default=None, action="store", help="optional output file")
    group1.add_argument("-p", "--prefer", dest="prefer", default=None, action="store_true",
                        help="In a case of color conversion conflict prefer bright colors")
    group1.add_argument("-n", "--no-prefer", dest="prefer", default=None, action="store_false",
                        help="In a case of color conversion conflict do not prefer bright colors")
    op.add_argument("-a", "--no-attrs", dest="attrs", help="do not save attributes",
                    action="store_false", default=True)
    group2.add_argument("-s", "--show", dest="color", help="show final image in color",
                        action="store_true", default=None)
    group2.add_argument("-b", "--show-bw", dest="color", help="show final image in black and white",
                        action="store_false", default=None)

    args = op.parse_args()

    # Open the file to convert..
    pic = zx.open(args.input, **vars(args))

    # output..
    if args.color is not None:
        pic.showZX(args.color)

    if args.output:
        pic.saveZX(args.output, args.attrs, args.linear)

# /* ex: set tabstop=8 softtabstop=0 shiftwidth=4 smarttab autoindent  /*
