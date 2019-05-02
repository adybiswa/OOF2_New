# -*- python -*-

# This software was produced by NIST, an agency of the U.S. government,
# and by statute is not subject to copyright in the United States.
# Recipients of this software assume all responsibilities associated
# with its operation, modification and maintenance. However, to
# facilitate maintenance we ask that before distributing modified
# versions of this software, you first contact the authors at
# oof_manager@nist.gov. 

from ooflib.common import color
from ooflib.common import debug
from ooflib.common.IO import colormap
from ooflib.common.IO import outputdevice
from ooflib.common.primitives import Rectangle
from ooflib.SWIG.common.coord import Coord
from ooflib.SWIG.common import lock
from ooflib.SWIG.common.IO import stringimage
from ooflib.common.primitives import iPoint
from ooflib.common.primitives import Point
import types
import string
import math
import weakref
import time

# Device for generating PDF output.  A previous version of this used
# to do PostScript output, but was abandoned because PS can't do
# transparency.

# Notes on PDF output:
# 
# In the PDFoutput device, as in the canvas, the output objects are
# divided up into layers.  Each layer is a "Form XObject", in PDF
# jargon, and directly contains the commands needed to draw it, and
# contains indirect references to any image objects that it might
# contain.  Partial (alpha) transparency is implemented as a layer
# property, rather than being an aspect of an object's color or a
# property of individual drawn objects (polygons, images, etc.).  The
# API is not as clear about this as it could be -- calling
# set_fillColorAlpha sets the fill color for the current graphics
# state, and the alpha for all objects in the current layer, including
# objects which have already been drawn with a different fill color.
# In practice, there is no problem with this, layers are geometrically
# simple and mono-colored in OOF, but the API will not generate errors
# if it is used more flexibly than expected. Also, each layer
# maintains a dictionary of the images it contains, and draws them in
# dictionary order.  Again, standard practice is that there is at most
# one image per layer.  If multiple images per layer are desired, they
# should be non-overlapping, otherwise images which occur later in the
# dictionary will occlude ones which occur earlier, and in general the
# user does not have control over the dictionary order.
#
# Unlike the PS output on which this code was based, each layer has
# its own graphics state, which is reset at the start of the layer, so
# graphics state changes (fill-color, etc.) do not carry over from one
# layer to another.  Line widths and fill colors must be specified on
# a per-layer basis.  Again, the calling sequence from OOF does this,
# but the API does not enforce it.
#
# The PDFobject does keep track of the current line color, because the
# PDFDot and PDFTriangle, although filled geometric objects, are
# filled with the current line color, not the fill color.  This is
# because they are "line-like" in the canvas, in the sense of scaling
# with the pixel size of the image, not with the physical size.  This
# feature is not apparent in PDF space.  These objects record the
# current line color at the time of their construction, and use it to
# fill themselves when they are drawn.
#
# The PDF specification does not require PDF consuming applications to
# understand exponential notation for numeric constants, and so it is
# not used here.  Instead, a large floating-point format is used.  The
# width of this may need adjusting, and users may run into
# difficulties if they use units such that the physical size of their
# computational domain is less than 1e-8 or so.
#
# TODO LATER: The file sizes generated by this code are larger than
# necessary.  Images could use compression to reduce the size of their
# data streams.  PDF consuming applications are supposed to have lots
# of nice filters.
# 
# Spec taken from "PDF Reference, 5th edition, Adobe Portable Document
# Format, version 1.6", Adobe Systems Inc., although none of what we
# have used requires anything later than PDF-1.4.  The book is
# available (in PDF form, of course) from
# <http://partners.adobe.com/public/developer/pdf/index_reference.html>.
# 
# PDF data structures and operators are copyright by Adobe Systems
# Incorporated, used with permission granted by section 1.5 of the
# PDF reference manual.

unitscale = {}
unitscale['points'] = 1
unitscale['inches'] = 72.00
unitscale['cm'] = 28.346456693

# Line width is always in points -- the factor expresses the width
# provided in points in the current user-coordinate-system units.
linewidth_factor = 1.0
linewidth_lock = lock.Lock()

def set_linewidth_factor(value):
    global linewidth_factor
    linewidth_lock.acquire()
    linewidth_factor = value
    linewidth_lock.release()

def get_linewidth_factor():
    global linewidth_factor
    linewidth_lock.acquire()
    res = linewidth_factor
    linewidth_lock.release()
    return res

# Scale factor is reset if the bbox is too far from unit size.
pdf_scale_factor = 1.0

# Primitive objects have __str__ methods which give their PDF form.
class PDFLineWidth:
    def __init__(self, w):
        self.width = w
    def __str__(self):
        return "%.10f w" % (self.width*pdf_scale_factor*
                            get_linewidth_factor())

class PDFColor:
    def __init__(self, color):
        self.color = color

class PDFLineColor(PDFColor):
    def __str__(self):
        return "%f %f %f RG" % self.color.rgb()

class PDFFillColor(PDFColor):
    def __str__(self):
        return "%f %f %f rg" % self.color.rgb()

class PDFSegment:
    def __init__(self, segment):
        self.segment = segment
    def __str__(self):
        return "%.10f %.10f m %.10f %.10f l S" % \
               (self.segment.start()[0]*pdf_scale_factor,
                self.segment.start()[1]*pdf_scale_factor,
                self.segment.end()[0]*pdf_scale_factor,
                self.segment.end()[1]*pdf_scale_factor)
    
class PDFCurve:
    def __init__(self, curve):
        self.curve = curve
    def ptsstring(self):
        res = []
        p0 = self.curve.points()[0]
        res.append("%.10f %.10f m" % (p0[0]*pdf_scale_factor,
                                      p0[1]*pdf_scale_factor))
        for pt in self.curve.points()[1:]:
            res.append("%.10f %.10f l" % (pt[0]*pdf_scale_factor,
                                          pt[1]*pdf_scale_factor))
        return res
    def __str__(self):
        strlist = self.ptsstring()
        strlist.append("S")
        return string.join(strlist, " ")

class PDFPolygon(PDFCurve):
    def __str__(self):
        strlist = self.ptsstring()
        strlist.append("s")
        return string.join(strlist, " ")

class PDFFilledPolygon(PDFCurve):
    def __str__(self):
        strlist = self.ptsstring()
        strlist.append("f")
        return string.join(strlist, " ")

class PDFTriangle(PDFFilledPolygon):
    def __init__(self, center,angle,size,color):
	self.center=center
	self.size=size
	self.angle=angle
        self.color=color
	PDFFilledPolygon.__init__(self,self)
    def points(self):
	r=self.size*get_linewidth_factor()*pdf_scale_factor/math.sqrt(3)
	return [self.center*pdf_scale_factor+Point(*[r*trig(2*math.pi*n/3-self.angle) for trig in (math.sin,math.cos)]) for n in range(3)]
    def __str__(self):
        lr = self.color.getRed()
        lg = self.color.getGreen()
        lb = self.color.getBlue()
        return "q %f %f %f rg %s Q" % (lr, lg, lb,
                                       PDFFilledPolygon.__str__(self))


class PDFCompoundPolygon:
    def __init__(self, polygons):
        self.polygons = polygons
    def write(self, file):
        for polygon in self.polygons:
            self.writepts(polygon,file)
        file.write("s")
    def ptsstring(self,polygon):
        res = []
        p0 = polygon.points()[0]
        res.append("%.10f %.10f m" % (p0[0]*pdf_scale_factor,
                                      p0[1]*pdf_scale_factor))
        for pt in polygon.points()[1:]:
            res.append("%.10f %.10f l" % (pt[0]*pdf_scale_factor,
                                          pt[1]*pdf_scale_factor))
        # Explicit closing point.
        res.append("%.10f %.10f l" % (p0[0]*pdf_scale_factor,
                                      p0[1]*pdf_scale_factor)) 
        return res

class PDFCompoundFilledPolygon(PDFCompoundPolygon):
    def __str__(self):
        strlist = []
        for polygon in self.polygons:
            strlist.extend(self.ptsstring(polygon))
        strlist.append("f")
        return string.join(strlist, " ")


class PDFCircle:
    def __init__(self, center, radius, filled):
	self.center=center
	self.radius=radius
	self.filled=filled
    def _radius(self):
	return self.radius
    def __str__(self):
        # Do by cubic bezier curves making each quadrant.
        arr = self._radius()*pdf_scale_factor
        controlpt = 0.55197*arr
        strlist = []
        scaled_center = self.center*pdf_scale_factor
        strlist.append("%.10f %.10f m" % \
                       (scaled_center[0]+arr, scaled_center[1]) )
        strlist.append("%.10f %.10f %.10f %.10f %.10f %.10f c" %
                       (scaled_center[0]+arr, scaled_center[1]+controlpt,
                        scaled_center[0]+controlpt, scaled_center[1]+arr,
                        scaled_center[0], scaled_center[1]+arr) )
        strlist.append("%.10f %.10f %.10f %.10f %.10f %.10f c" %
                       (scaled_center[0]-controlpt, scaled_center[1]+arr,
                        scaled_center[0]-arr, scaled_center[1]+controlpt,
                        scaled_center[0]-arr, scaled_center[1]) )
        strlist.append("%.10f %.10f %.10f %.10f %.10f %.10f c" %
                       (scaled_center[0]-arr, scaled_center[1]-controlpt,
                        scaled_center[0]-controlpt, scaled_center[1]-arr,
                        scaled_center[0], scaled_center[1]-arr) )
        strlist.append("%.10f %.10f %.10f %.10f %.10f %.10f c" %
                       (scaled_center[0]+controlpt, scaled_center[1]-arr,
                        scaled_center[0]+arr, scaled_center[1]-controlpt,
                        scaled_center[0]+arr, scaled_center[1]) )
        if self.filled:
            strlist.append("f")
        else:
            strlist.append("S")
        return string.join(strlist, " ")

# A PDFDot is filled, but with the *line* color current when it's created.
class PDFDot(PDFCircle):
    def __init__(self,center,radius,color):
	PDFCircle.__init__(self,center,radius,1)
        self.color = color
    def _radius(self):
	return self.radius*get_linewidth_factor()
    def __str__(self):
        lr = self.color.getRed()
        lg = self.color.getGreen()
        lb = self.color.getBlue()
        return "q %f %f %f rg %s Q" % (lr, lg, lb, PDFCircle.__str__(self) )

# A comment is not "primitive" in the sense that it has no requirement
# to be enclosed in another object.  
class PDFComment:
    def __init__(self, comment):
        self.comment = comment
    def __str__(self):
        return self.comment



# Base class for all the things which are PDFXobjects.  The base class
# has book-keeping information.  "pdfid" is guaranteed to be an
# integer.
class PDFXObject:
    def __init__(self, pdfid):
        self.pdfid = pdfid
        self.commands=[]
        self.comments=[]
        self.alpha=1.0
        self.active = 1
    def activate(self):
        self.active = 1
    def deactivate(self):
        self.active = None
    def add_command(self, command):
        if self.active:
            self.commands.append(command)
    def add_comment(self, comment):
        self.comments.append(comment)
    def set_alpha(self, alpha):
        self.alpha = alpha


# Layers are written to the file as PDF Form objects.  The "images"
# attribute is a dictionary, index by pdfid, of the PDFImage objects
# present in this layer.  Images are drawn before any graphics
# commands are executed, and are drawn in reverse dictionary order.
# In practice, layers typically contain either one image, or drawing
# commands and no images, so this scheme doesn't break anything.
class PDFLayerObject(PDFXObject):
    def __init__(self, pdfid):
        PDFXObject.__init__(self, pdfid)
        self.images = {}
        
    def add_image(self, image):
        if self.active:
            self.images[image.pdfid]=image
            
    def write(self, pdf):
        # Construct the commands for drawing the images.
        for (idx, image) in self.images.items():
            draw_image = "q %s /image%d Do Q" % (image.predo(), idx)
            self.commands.insert(0,draw_image)

        pdf.line("%d 0 obj" % self.pdfid)
        pdf.line("<<")
        pdf.line("  /Type /XObject")
        pdf.line("  /Subtype /Form")
        pdf.line("  /FormType 1")
        pdf.line("  /BBox %s" %  pdf.bbox)
        pdf.line("  /Matrix %s" % pdf.matrix)
        if self.alpha!=1.0 or len(self.images)>0:
            pdf.line("  /Resources <<") 
        if len(self.images)>0:
            pdf.line("    /XObject <<")
            for k in self.images:
                pdf.line("      /image%(key)d %(key)d 0 R" % {"key":k} )
            pdf.line("    >>")
        if self.alpha!=1.0:
            pdf.line("    /ExtGState <<")
            pdf.line("      /trans << /CA %(alpha)f /ca %(alpha)f >>" %
                     {"alpha" : self.alpha } )
            pdf.line("    >>")
        if self.alpha!=1.0 or len(self.images)>0:
            pdf.line("  >>") # Close the Resource dictionary.
        if self.alpha!=1.0: # In transparent case, also make a Group entry.
            pdf.line("  /Group <<")
            pdf.line("    /Type /Group")
            pdf.line("    /S /Transparency")
            pdf.line("    /I false")
            pdf.line("    /K true")
            pdf.line("  >>")
            self.commands.insert(0,"/trans gs")
        streamstring = string.join(map(str, self.commands), " ")
        size = len(streamstring)
        pdf.line("  /Length %d" % size)
        pdf.line(">>")
        pdf.line("stream")
        pdf.write(streamstring+"\r\n")
        pdf.line("endstream")
        pdf.line("endobj")
                     

class PDFImageBase(PDFXObject):
    def predo(self):
        return "%.10f 0 0 %.10f %.10f %.10f cm" % (
            self.size[0]*pdf_scale_factor,
            self.size[1]*pdf_scale_factor,
            self.offset[0]*pdf_scale_factor,
            self.offset[1]*pdf_scale_factor)

# For an Image or ShapedImage, the "commands" are the data stream that
# make up the image.
class PDFImageObject(PDFImageBase):
    def __init__(self, pdfid, image, offset, size):
        PDFXObject.__init__(self, pdfid)
	self.offset=offset
	self.size=size    # "Physical" size.
        self.pixel_size = image.sizeInPixels()
        strimg = stringimage.StringImage(self.pixel_size, self.size)
        image.fillstringimage(strimg)
        self.commands.append(strimg.hexstringimage())
    def write(self, pdf):
        # For images, there's just the one "command" string with all
        # the data in it.
        stringstream = self.commands[0]+">" # EOD marker for filter.
        size = len(stringstream)
        pdf.line("%d 0 obj" % self.pdfid)
        pdf.line("<<")
        pdf.line("  /Type /XObject")
        pdf.line("  /Subtype /Image")
        pdf.line("  /Filter /ASCIIHexDecode")
        pdf.line("  /Length %d" % size)
        pdf.line("  /Width %d" % self.pixel_size[0])
        pdf.line("  /Height %d" % self.pixel_size[1])
        pdf.line("  /ColorSpace /DeviceRGB")
        pdf.line("  /BitsPerComponent 8")
        pdf.line(">>")
        pdf.line("stream")
        pdf.write(stringstream+"\r\n")
        pdf.line("endstream")
        pdf.line("endobj")
        
        
class PDFShapedImageObject(PDFImageBase): # used by draw_alpha_image
    def __init__(self, pdfid, image, offset, size, shapecolor):
        PDFXObject.__init__(self, pdfid)
	self.offset=offset
	self.size=size
	self.shapecolor=shapecolor
        self.pixel_size = image.sizeInPixels()
        strimg = stringimage.StringImage(self.pixel_size, self.size)
        image.fillstringimage(strimg)
        self.commands.append(strimg.hexstringimage())
    def write(self, pdf):
        stringstream = self.commands[0]+">" # EOD marker.
        size = len(stringstream)
        pdf.line("%d 0 obj" % self.pdfid)
        pdf.line("<<")
        pdf.line("  /Type /XObject")
        pdf.line("  /Subtype /Image")
        pdf.line("  /Filter /ASCIIHexDecode")
        pdf.line("  /Length %d" % size)
        pdf.line("  /Width %d" % self.pixel_size[0])
        pdf.line("  /Height %d" % self.pixel_size[1])
        pdf.line("  /Mask [%(r)d %(r)d %(g)d %(g)d %(b)d %(b)d]" %
                 { "r" : self.shapecolor.getRed()*255,
                   "g" : self.shapecolor.getGreen()*255,
                   "b" : self.shapecolor.getBlue()*255 }  )
        pdf.line("  /ColorSpace /DeviceRGB")
        pdf.line("  /BitsPerComponent 8")
        pdf.line(">>")
        pdf.line("stream")
        pdf.write(stringstream+"\r\n")
        pdf.line("endstream")
        pdf.line("endobj")


# This is the layer object that gets passed out to the caller, not the
# internal representation of a layer -- the latter is PDFLayerObject,
# and is a subclass of PDFXObject.
class PDFLayer(outputdevice.NullLayer):
    # PDFLayer stores a *weak* reference to the device, because the
    # layers are stored in weak key dictionaries in the Display, keyed
    # by the device.  Keeping a reference to the device here would
    # break that mechanism.  TODO LATER: implement a less fragile
    # design.
    # The pdfid uniquely identifies this layer in the PDF device.
    def __init__(self, device, pdfid):
        self.device = weakref.ref(device)
        self.pdfid = pdfid 
    def hide(self):
        self.device().deactivate_layer(self.pdfid)
    def make_current(self):
        self.device().set_current_layer(self.pdfid)





#####################################################################


class PDFoutput(outputdevice.OutputDevice):
    def __init__(self,
                 filename,
                 margin=0.05,        # Fractional whitespace on page bdy.
                 frame=0.05,         # Buffer btw. bbpx and image
                 pageheight=11.0,      # height of page
                 pagewidth=8.5,        # width of page
                 units='inches',       # units for the above
                 linewidthfactor=1.0,
                 format='portrait'):    # 'portrait' or 'landscape'

        outputdevice.OutputDevice.__init__(self)

        # List of PDFImageObject instances included in this document.
        self.images = []

        # List of PDFLayerObject instances, which refer to the images.
        self.layers = []

	self.clear()
        self.frame=0.05

        if not units in unitscale:
            raise "PDFoutput: unknown units"
        if format != 'landscape' and format != 'portrait':
            raise "PDFoutput: unknown page format"

        self.file = open(filename, 'wb')

        # Convert dimensions to points
        scalefactor = unitscale[units]
        self.pageh = pageheight * scalefactor
        self.pagew = pagewidth * scalefactor
        self.drawing_height = int(self.pageh/(1.0+2.0*margin))
        self.drawing_width = int(self.pagew/(1.0+2.0*margin))
        self.linewidthfactor = linewidthfactor
        
        self.format = format

        # Need to keep track of line colors because PDFDot and
        # Triangle objects use the line color for filling.
        self.current_line_width=0
        self.current_line_color=None
        
        self.background_color = color.white
        self.colormap = colormap.GrayMap()

        # Not much else can be done until the bounding box is
        # established, so the header and definitions are written when
        # "show" is called, and the actual range is known.


    def has_alpha(self):
        return True

    def expand_range(self, obj):
        if self.range is None:
            self.range = obj.enclosing_rectangle()
        else:
            self.range.swallow(obj)


    ####

    def set_background(self, color):
        self.background_color = color
        

    ###########################################
    ## Drawing operations.
    ###########################################

    def clear(self):
        # List of the file locations of all the PDFXObject subtypes in
        # the file.  Filled in as objects are written, then used to
        # construct the xref trailer.  The first seven objects are: 0
        # (reserved), 1 (Resource dictionary), 2 (Page Tree), 3
        # (Page), 4 (Content Stream), 5 (Catalog), and 6 (Info
        # Dictionary).
        self.objects = [0,0,0,0,0,0,0]
        self.images = []
        self.layers = []
        self.range = None
        self.current_layer = None
        
        self.proc_set_id = 1
        self.page_root_id = 2
        self.page_obj_id = 3
        self.content_stream_id = 4
        self.catalog_id = 5
        self.info_id = 6

    def write(self, data):
        self.count += len(data)
        self.file.write(data)
        
    def line(self, data):
        data += "\r\n"
        self.write(data)
        
        
    def show(self):
        global pdf_scale_factor
        if self.range is not None and not self.file.closed:
            xmax = self.range.xmax()
            xmin = self.range.xmin()
            ymax = self.range.ymax()
            ymin = self.range.ymin()

            dx = xmax - xmin
            dy = ymax - ymin

            # Magic numbers: PDF files don't understand scientific
            # notation, but we want to draw in the physical-units
            # space, which could be very small, or very large.  So, if
            # it's too small or too large compared to unity, rescale
            # everything so the PDF stuff is near unity.
            if (dx<1.e-6) or (dy<1.e-6) or (dx>1.e6) or (dy>1.e6):
                if dx<dy:
                    pdf_scale_factor = 1.0/dx
                else:
                    pdf_scale_factor = 1.0/dy

            dx *= pdf_scale_factor
            dy *= pdf_scale_factor
            xmin *= pdf_scale_factor
            ymin *= pdf_scale_factor
            xmax *= pdf_scale_factor
            ymax *= pdf_scale_factor

            frame_dx = dx*(1.0+2.0*self.frame)
            frame_dy = dy*(1.0+2.0*self.frame)
            
            # The geometry of this is a bit complicated -- there is a
            # margin, of fractional size self.frame, between the box
            # inside of which all the drawing occurs, and the
            # PostScript bounding box.  The bounding box is larger
            # than the actually-drawn area.  The background color is
            # drawn over the entire bounding box, and so this margin
            # gets the background color, but no other data.
            
            # After all the coordinate transformations, the point
            # (0,0) is the lower left corner of the drawing area
            # (*not* the bounding box).

            h_over_w = float(self.drawing_height)/float(self.drawing_width)
            w_over_h = 1.0/h_over_w
            if self.format == 'portrait':
                if (dy/dx) > h_over_w:
                    # Aspect ratio is skinnier than page, height-limited.
                    points_per_unit = float(self.drawing_height)/frame_dy
                    self.height = self.drawing_height
                    self.width = self.height*(dx/dy)
                else:
                    # Width-limited.
                    points_per_unit = float(self.drawing_width)/frame_dx
                    self.width = self.drawing_width
                    self.height = self.width*(dy/dx)
                image_height = dy*points_per_unit
                image_width = dx*points_per_unit
            elif self.format == 'landscape':
                if (dy/dx) > w_over_h:
                    # Height-limited, but "height" is along drawing_width.
                    points_per_unit = float(self.drawing_width)/frame_dy
                    self.height = self.drawing_width
                    self.width = self.height*(dx/dy)
                else:
                    # Width-limited
                    points_per_unit = float(self.drawing_height)/frame_dx
                    self.width = self.drawing_height
                    self.height = self.width*(dy/dx)
                image_height = dx*points_per_unit
                image_width = dy*points_per_unit
            # Unrecognized format is already checked for.
                    

            self.pointsize = 1.0/points_per_unit
            set_linewidth_factor(self.linewidthfactor*self.pointsize)


            # Bounding box in points in the page-space.  This is used
            # directly in "show" to draw the background color, and is
            # also a useful intermediate step for constructing the
            # form-specific transformation matrices.
            if self.format == 'portrait':
                bbxmin = int(0.5*(self.pagew - self.width))
                bbxmax = int(bbxmin + self.width)
                bbymin = int(0.5*(self.pageh - self.height))
                bbymax = int(bbymin + self.height)
            elif self.format == 'landscape':
                bbxmin = int(0.5*(self.pagew - self.height))
                bbxmax = int(bbxmin + self.height)
                bbymin = int(0.5*(self.pageh - self.width))
                bbymax = int(bbymin + self.width)

            frame_x_in_pts = ((frame_dx-dx)/2.0)*points_per_unit
            frame_y_in_pts = ((frame_dy-dy)/2.0)*points_per_unit
            if self.format == 'portrait':
                # (xmin,ymin) maps to (bbxmin+fx,bbymin+fy)
                # (xmax,ymax) maps to (bbxmax-fx,bbymax-fy)
                sx = (bbxmax-bbxmin-2.0*frame_x_in_pts)/dx
                sy = (bbymax-bbymin-2.0*frame_y_in_pts)/dy
                tx = (bbxmin*xmax-bbxmax*xmin+frame_x_in_pts*(xmax+xmin))/dx
                ty = (bbymin*ymax-bbymax*ymin+frame_y_in_pts*(ymax+ymin))/dy
                self.matrix="[%f 0 0 %f %f %f]" % (sx,sy,tx,ty)
            elif self.format == 'landscape':
                # (xmin,ymin) maps to (bbxmax-fy,bbymin+fx)
                # (xmax,ymin) maps to (bbxmax-fy,bbymax-fx)
                # (xmin,ymax) maps to (bbxmin+fy,bbymin+fx)
                tx = (bbxmax*ymax-bbxmin*ymin-frame_y_in_pts*(ymax+ymin))/dy
                ty = (bbymin*xmax-bbymax*xmin+frame_x_in_pts*(xmax+xmin))/dx
                ry = (bbymax-bbymin-2.0*frame_x_in_pts)/dx
                rx = (bbxmin-bbxmax+2.0*frame_y_in_pts)/dy
                self.matrix="[0 %f %f 0 %f %f]" % (rx,ry,tx,ty)

            # PDFs want a bounding box in "Form Space", which for us
            # is the physical-unit space.
            fbxmin = xmin-self.frame*dx
            fbxmax = xmax+self.frame*dx
            fbymin = ymin-self.frame*dy
            fbymax = ymax+self.frame*dy
            self.bbox = "[%f %f %f %f]" % (fbxmin,fbymin,fbxmax,fbymax)

            # Datestamp, as a string, in GMT, in spec-recommended form.
            self.datestamp = time.strftime("%Y%m%d%H%M%SZ", time.gmtime())

            # Actually start writing the file.
            self.count = 0
            self.line("%PDF-1.4")
            # Binary block, so auto-detecting transfer stuff will work.
            self.line("%\xfe\xed\xbe\xef")
            self.line("% PDF data structures and operators copyright")
            self.line("%     by Adobe Systems Incorporated.")

            # Procedure set 
            self.objects[self.proc_set_id]=self.count
            self.line("%d 0 obj" % self.proc_set_id)
            self.line("[/PDF /Text /ImageC /ImageB /ImageI]")
            self.line("endobj")

            # Write the info block near the top, so human readers have
            # a chance to see it.
            self.objects[self.info_id]=self.count
            self.line("%d 0 obj" % self.info_id)
            self.line("<<")
            self.line("  /Producer (OOF2)")
            self.line("  /CreationDate (D:%s)" % self.datestamp)
            self.line(">>")
            self.line("endobj")
            
            # Write out the images.
            for img in self.images:
                self.objects[img.pdfid]=self.count
                img.write(self)

            # And the layer objects.
            for lob in self.layers:
                for com in lob.comments:
                    self.write("\r\n%% %s\r\n" % str(com))
                self.objects[lob.pdfid]=self.count
                lob.write(self)

            # Page root.
            self.objects[self.page_root_id]=self.count
            self.line("%d 0 obj" % self.page_root_id)
            self.line("<<")
            self.line("  /Type /Pages")
            self.line("  /Kids [ %d 0 R ]" % self.page_obj_id)
            self.line("  /Count 1")
            self.line(">>")
            self.line("endobj")

            # Page object.  This has the layers in it.
            self.objects[self.page_obj_id]=self.count
            self.line("%d 0 obj" % self.page_obj_id)
            self.line("<<")
            self.line("  /Type /Page")
            self.line("  /Parent %d 0 R" % self.page_root_id)
            self.line("  /Resources << ")
            self.line("    /ProcSet %d 0 R" % self.proc_set_id)
            self.line("    /XObject <<")
            for lay in self.layers:
                self.line("      /layer%(id)d %(id)d 0 R" %
                          { "id" : lay.pdfid } )
            self.line("    >>") # End of XObject dictionary.
            self.line("  >>") # End of Resources dictionary.
            self.line("  /MediaBox [0 0 612 792]")
            self.line("  /Contents %d 0 R" % self.content_stream_id)
            self.line(">>")
            self.line("endobj")

            # The content stream -- put the layers on the page, but
            # first do the background.
            br = self.background_color.getRed()
            bg = self.background_color.getGreen()
            bb = self.background_color.getBlue()
            streamdata = ["q %f %f %f rg %f %f m %f %f l %f %f l %f %f l f Q" %
                          (br,bg,bb, bbxmin,bbymin, bbxmax,bbymin,
                           bbxmax,bbymax, bbxmin,bbymax)]
            for lay in self.layers:
                streamdata.append("/layer%d Do" % lay.pdfid)
            streamstring = string.join(streamdata, "\r\n")
            self.objects[self.content_stream_id]=self.count
            self.line("%d 0 obj" % self.content_stream_id)
            self.line("<<")
            self.line("  /Length %d" % len(streamstring))
            self.line(">>")
            self.line("stream")
            self.write(streamstring+"\r\n")
            self.line("endstream")
            self.line("endobj")

            # Catalog.
            self.objects[self.catalog_id]=self.count
            self.line("%d 0 obj" % self.catalog_id)
            self.line("<<")
            self.line("  /Type /Catalog")
            self.line("  /Pages %d 0 R" % self.page_root_id)
            self.line(">>")
            self.line("endobj")

            # Required PDF trailing stuff -- cross-reference table.
            xrefpos = self.count
            self.line("xref")
            self.line("%d %d" % (0, len(self.objects) ))
            self.line("0000000000 65535 f")
            for i in range(1,len(self.objects)):
                self.line("%010d 00000 n" % self.objects[i])

            self.line("trailer")
            self.line("<<")
            self.line("  /Size %d" % len(self.objects))
            self.line("  /Root %d 0 R" % self.catalog_id)
            self.line("  /Info %d 0 R" % self.info_id)
            self.line("  /ID [ (OOF2 PDF Output) (%s) ]" % self.datestamp)
            self.line(">>")
            
            self.line("startxref")
            self.line("%d" % xrefpos)
            self.line("%%EOF")

            self.file.close()


    def append(self, obj):
        if self.current_layer:
            self.current_layer.add_command(obj)

    def begin_layer(self):
        pdfid = len(self.objects)
        self.objects.append(0) # Place-holder.
        new_layer = PDFLayerObject(pdfid)
        self.layers.append(new_layer)
        if not self.current_layer:
            self.current_layer=new_layer
        else:
            print "New PDF layer started while old layer not closed!"
        return PDFLayer(self, pdfid)

    def end_layer(self):
        self.current_layer = None

    def deactivate_layer(self, pdfid):
        for ell in self.layers:
            if ell.pdfid == pdfid:
                ell.deactivate()
                return
        print "Layer not found in deactivate_layer."
        
    def set_current_layer(self, pdfid):
        for ell in self.layers:
            if ell.pdfid == pdfid:
                self.current_layer = ell
                break
        else:
            print "Layer not found in set_current_layer."
        self.current_layer.activate()
        
    def set_lineWidth(self, w):
        self.current_layer.add_command(PDFLineWidth(w))
        self.current_line_width = w

    def set_lineColor(self, x):
        if type(x)==type(1.0):
            color = self.colormap(x)
        else:
            color = x
        self.current_layer.add_command(PDFLineColor(color))
        self.current_line_color = color

    def set_fillColor(self, x):
        if type(x)==type(1.0):
            color = self.colormap(x)
        else:
            color = x
        self.current_layer.add_command(PDFFillColor(color))

    def set_fillColorAlpha(self, color, alpha):
        if type(color)==type(1.0):
            color = self.colormap(color)
        self.current_layer.add_command(PDFFillColor(color))
        self.current_layer.set_alpha(alpha/255.0)

    def draw_segment(self, segment):
        self.expand_range(segment)
        self.current_layer.add_command(PDFSegment(segment))

    def draw_dot(self,dot):
	self.current_layer.add_command(PDFDot(dot,
                                              self.current_line_width,
                                              self.current_line_color) )
	# r=self.current_line_width*self.linewidthfactor
	# self.expand_range(Rectangle(Coord(dot[0]-r,dot[1]-r),
        #                             Coord(dot[0]+r,dot[1]+r)))

    # TODO LATER: The draw_dot and draw_triangle expand_range
    # computations are wrong.  self.linewidthfactor isn't set
    # correctly until "show"-time, at which time the size of the
    # triangle in physical units becomes known, so we can't compute
    # the right range here.  So, we don't compute any range at all,
    # because dots and triangles are usually small, and there should
    # be enough margin to not clip them.  This may actually be
    # acceptable.

    def draw_triangle(self,center,angle):
	self.current_layer.add_command(
            PDFTriangle(center, angle,
                        self.current_line_width,
                        self.current_line_color))
	# r=(self.current_line_width*self.linewidthfactor)/math.sqrt(3)
	# self.expand_range(Rectangle(Coord(center[0]-r,center[1]-r),
        #                             Coord(center[0]+r,center[1]+r)))

    def draw_curve(self, curve):
        self.expand_range(curve)
        self.current_layer.add_command(PDFCurve(curve))

    def draw_polygon(self, polygon):
        if type(polygon) == types.ListType:
            for pgon in polygon:
                self.expand_range(pgon)
            self.current_layer.add_command(PDFCompoundPolygon(polygon))
        else:
            self.expand_range(polygon)
            self.current_layer.add_command(PDFPolygon(polygon))

    def fill_polygon(self, polygon):
        if type(polygon) == types.ListType:
            for pgon in polygon:
                self.expand_range(pgon)
            self.current_layer.add_command(PDFCompoundFilledPolygon(polygon))
        else:
            self.expand_range(polygon)
            self.current_layer.add_command(PDFFilledPolygon(polygon))

    # def draw_circle(self, center, radius):
    #     self.current_layer.add_command(PDFCircle(center,radius,0))
    #     r=radius
    #     self.expand_range(Rectangle(Coord(center[0]-r,center[1]-r),
    #                                 Coord(center[0]+r,center[1]+r)))

    # def fill_circle(self, center, radius):
    #     self.current_layer.add_command(PDFCircle(center,radius,1))
    #     r=radius
    #     self.expand_range(Rectangle(Coord(center[0]-r,center[1]-r),
    #                                 Coord(center[0]+r,center[1]+r)))

    def draw_image(self,image,offset,size):
	if image.sizeInPixels()==iPoint(0,0):
            return
        pdfid = len(self.objects)
        self.objects.append(0) # Place-holder.
        newimage = PDFImageObject(pdfid,image,offset,size)
        self.images.append(newimage)
        self.current_layer.add_image(newimage)
        self.expand_range(Rectangle(offset,Coord(offset[0]+size[0],
                                                 offset[1]+size[1])))

    # Draws a shaped image and sets the alpha of the current layer.
    def draw_alpha_image(self, bitmap, offset, size):
        if bitmap.sizeInPixels()==iPoint(0,0):
            return
        pdfid = len(self.objects)
        self.objects.append(0) # Place-holder
        maskcolor = bitmap.getBG()
        newimage = PDFShapedImageObject(pdfid,bitmap,offset,size,maskcolor)
        self.images.append(newimage)
        self.current_layer.add_image(newimage)
        self.current_layer.set_alpha(bitmap.getTintAlpha())
        self.expand_range(Rectangle(offset,Coord(offset[0]+size[0],
                                                 offset[1]+size[1])) )
        

    def comment(self, remark):
        self.current_layer.add_comment(PDFComment(remark))

