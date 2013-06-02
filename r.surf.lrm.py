#!/usr/bin/env python

############################################################################
#
# MODULE:	    r.surf.lrm
#
# AUTHOR(S):    Eric Goddard, egoddard@memphis.edu
#
# PURPOSE:	    Create a Local Relief Model from input DEM based on Hesse
#               (2010), with additional help from Rebecca Bennett's bash
#               script.
#
# COPYRIGHT:	(C) 2013 Eric Goddard
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
# REFERENCES:
#       2011  Bennett, Rebecca.  Archaeological Remote Sensing: Visualisation
#               and analysis of grass-dominated environments using airborne
#               laser scanning and digital spectra data. Unpublished PhD
#               Thesis. Electronic Document, http://eprints.bournemouth.ac.uk/
#               20459/1/Bennett%2C_Rebecca_PhD_Thesis_2011.pdf,
#               Accessed 25 February 2013.
#
#
#       2010  Hesse, Ralf. LiDAR-derived Local Relief Models - a new tool for
#               archaeological prospection. Archaeological Prospection
#               17:67-72.
#
#
#############################################################################

#%module
#%  description: Creates a Local Relief Model from input raster.
#%  keywords: lrm
#%  keywords: lidar
#%  overwrite: yes
#%end
#%option G_OPT_R_INPUT
#%  key:input_map
#%  description: Select input raster
#%  required: yes
#%end
#%option
#%  key: output_prefix
#%  description: Prefix for output LRM files
#%  required: yes
#%end
#%option
#%  key: kernel
#%  type: integer
#%  description: The kernel size to be used in the low pass filter.
#%  required: no
#%  answer: 25
#%end

import sys
import os
import grass.script as grass

if "GISBASE" not in os.environ:
    print "You must be in GRASS GIS to run this program."
    sys.exit(1)


def main():

    input_map = options['input_map']
    output_prefix = options['output_prefix']
    kernel = options['kernel']

    #Processing files
    lp_out = "%s_lpf" % output_prefix
    lp_subtract = "%s_lpf_difference" % output_prefix
    LP_contour = "%s_diff_contour" % output_prefix
    LP_points = "%s_points" % LP_contour
    LP_purged = "%s_purged" % output_prefix
    lrm_output = "%s_lrm" % output_prefix

    #Run the low pass filter on input map
    grass.message("Running low pass filter on %s." % input_map)
    grass.run_command("r.neighbors", input=input_map, output=lp_out,
                      size=kernel, method="average")

    #Subtract the result of the low pass filter from the input map
    grass.message("Subtracting low pass from DEM...")
    grass.mapcalc("$lp_subtract = $input_map - $lp_out",
                  lp_subtract=lp_subtract, input_map=input_map,
                  lp_out=lp_out)

    #Extract the zero contours
    grass.message("Extracting zero contours from low pass difference...")
    grass.run_command("r.contour", input=lp_subtract, output=LP_contour,
                      minlevel="0", maxlevel="0", step="10")
    grass.run_command("v.to.points", input=LP_contour, llayer="1", type="line",
                      output=LP_points, dmax="10")
    grass.run_command("v.what.rast", map=LP_points, raster=input_map,
                      layer="2", column="along")

    #Get mean distance between points to optimize spline interpolation
    meanDist = grass.parse_command("v.surf.bspline", flags="e",
                                   input=LP_points, raster_output=LP_purged,
                                   layer="2", column="along",
                                   method="linear")

    #The -e flag on v.surf.bspline returns a length 1 dictionary key string
    #containing the Estimated point density and mean distance between points,
    #with the mean distance between points as the last value. Extract the
    #dictionary key, split it into a list using space as a separator, and
    #the last element in the list is the mean distance between points.
    #Double to get length of spline step for interpolation.
    splineStep = round(float(meanDist.keys()[0].split(" ")[-1])) * 2

    grass.message("Interpolating purged surface using a spline step value of \
                  %.0f..." % splineStep)
    #Interpolate using v.surf.bspline with meanDist * 2 as sie and sin
    grass.run_command("v.surf.bspline", input=LP_points,
                      raster_output=LP_purged, layer="2", sie=splineStep,
                      sin=splineStep, column="along", method="bilinear")

    #Subtract the purged surface from input surface to get the local relief and
    #apply a grey color table.
    grass.message("Creating Local Relief Model...")
    grass.mapcalc("$lrm_output = $input_map - $LP_purged",
                  lrm_output=lrm_output, input_map=input_map,
                  LP_purged=LP_purged)
    grass.run_command("r.colors", map=lrm_output, color="differences")

    grass.message("Done.")

if __name__ == "__main__":
    options, flags = grass.parser()
    main()
