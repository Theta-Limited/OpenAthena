"""
find_me_mode.py

This file is for an alternate targeting mode where target match locations are provided in relative terms (bearing, distance, elevation change) for use by on the ground search and rescue teams, short-distance indirect fire teams (e.g. mortars) and the like

nA single fixed location may be specified either using WGS84 Geodetic Lat/Lon or NATO MGRS (with altitude optional).

If desired, Magnetic Declination can be optionally specified so that the target bearing will be output in magnetic heading (instead of true heading), e.g. for use with a handheld analog compass. This is not necessary for most digital compasses (e.g. a smartphone)

Only intended for short range distances, otherwise will be inaccurate (curvature of the earth, great circle distance, etc.)

"""
import sys
import os
import time
import math
import numpy
from math import sin, asin, cos, atan2, sqrt
import decimal # more float precision with Decimal objects

from osgeo import gdal # en.wikipedia.org/wiki/GDAL

# https://pypi.org/project/mgrs/
import mgrs # Military Grid ref converter

from PIL import Image
from PIL import ExifTags

import parseImage
from parseGeoTIFF import getAltFromLatLon, binarySearchNearest
from getTarget import *

def find_me_mode():
    images = []

    elevationData = None
    x0, dx, dxdy, y0, dydx, dy = [None] * 6
    x1 = y1 = None
    nrows = ncols = None
    xParams = yParams = [None] * 4
    geofilename = None

    m = mgrs.MGRS()

    lat = None
    lon = None
    my_mgrs = None
    alt = None
    mag = 0.0
    directory = None

    # jpl.nasa.gov/edu/news/2016/3/16/how-many-decimals-of-pi-do-we-really-need
    decimal.getcontext().prec = 30

    if len(sys.argv) <= 1:
        errstr = f'FATAL ERROR: no location specified, please use --lat YY.YYYY --lon XX.XXXX (WGS84)'
        sys.exit(errstr)

    for i in range(len(sys.argv)):
        segment = sys.argv[i]
        if segment.lower() == "--lat":
            if i + 1 >= len(sys.argv):
                sys.exit("FATAL ERROR: expected value after '--lat'")
            else:
                lat = sys.argv[i + 1]
            try:
                lat = float(lat)
            except ValueError:
                errstr = f"FATAL ERROR: expected Latitude, got: {lat}"
                sys.exit(errstr)
        elif segment.lower() == "--lon":
            if i + 1 >= len(sys.argv):
                sys.exit("FATAL ERROR: expected value after '--lon'")
            else:
                lon = sys.argv[i + 1]
            try:
                lon = float(lon)
            except ValueError:
                errstr = f"FATAL ERROR: expected Longitude, got: {lon}"
                sys.exit(errstr)
        elif segment.lower() == "--mgrs":
            if i + 1 >= len(sys.argv):
                sys.exit("FATAL ERROR: expected value after '--mgrs'")
            else:
                my_mgrs = sys.argv[i + 1]
            try:
                lat, lon = m.toLatLon(my_mgrs)
            except:
                errstr = f"FATAL ERROR: expected NATO MGRS, got: {my_mgrs}"
                sys.exit(errstr)
        elif segment.lower() == "--mag":
            if i + 1 >= len(sys.argv):
                sys.exit("FATAL ERROR: expected value after '--mag'")
            else:
                mag = sys.argv[i + 1]

            try:
                mag = float(mag)
            except ValueError:
                errstr = f"FATAL ERROR: expected compass mag declination, got: {mag}"
                sys.exit(errstr)

            if mag < -180.0 or mag > 360.0:
                errstr = f"FATAL ERROR: compas mag declination out of range"
                sys.exit(errstr)
        elif segment.lower() == "--alt":
            if i + 1 >= len(sys.argv):
                sys.exit("Fatal ERROR: expected value after '--alt'")
            else:
                alt = sys.argv[i + 1]
            try:
                alt = float(alt)
            except ValueError:
                errstr = f"FATAL ERROR: expected WGS84 altitude, got: {alt}"
                sys.exit(errstr)
        elif segment.lower() == "--dir":
            if i + 1 >= len(sys.argv):
                sys.exit("FATAL ERROR: expected path after '--dir'")
            else:
                directory = sys.argv[i + 1]
            try:
                if not os.path.exists(directory):
                    print(f"FATAL ERROR: {directory} does not exist!")
                    raise OSError()
                directory = os.path.expanduser(directory) # expand out ~ (Unix)
                directory = os.path.expandvars(directory) # expand like %UserProfile% (Win) ${name} (Unix)
            except OSError:
                errstr = f"FATAL ERROR: path {directory} could not be processed"
                sys.exit(errstr)

        elif segment.split('.')[-1].lower() == "tif":
            geofilename = segment
            elevationData, (x0, dx, dxdy, y0, dydx, dy) = getGeoFileFromString(geofilename)
            nrows, ncols = elevationData.shape
            x1 = x0 + dx * ncols
            y1 = y0 + dy * nrows
            ensureValidGeotiff(dxdy, dydx)
            xParams = (x0, x1, dx, ncols)
            yParams = (y0, y1, dy, nrows)

    #end for loop

    mag = -1 * mag # instead of magnetic -> true heading, we go true -> magnetic (so we must invert)
    if mag != 0.0:
        warnStr = '\033[1;31;m' #ANSI escape sequence, bold and red
        warnStr += f"WARNING: adjusting target headings by {'+' if mag > 0 else ''}{mag}° for use with analog compass\n"
        warnStr += "    please ensure this direction is correct and your compass decl. is set to 0°"
        warnStr +="\033[0;0m" #ANSI escape sequence, reset terminal to normal colors
        warnStr +="\n"
        print(warnStr)

    if lat is None or lon is None:
        errstr = f'FATAL ERROR: no location specified, please use --lat YY.YYYY --lon XX.XXXX (WGS84)'
        sys.exit(errstr)

    if elevationData is None:
        errstr = "FATAL ERROR: no valid GeoTIFF (.tif) Digital Elevation Model provided!"
        sys.exit(errstr)

    if (lat > y0 or lat < y1) or (lon < x0 or lon > x1):
        errstr = f"FATAL ERROR: {round(lat,6)}, {round(lon,6)} is outside of GeoTIFF coverage area\n"
        errstr += f"    Please ensure you are using the correct file\n"
        errstr += f"    Your Location: {round(lat,4)}, {round(lon,4)}\n"
        errstr += f"    {geofilename}:\n"
        errstr += f"        {round(y1,6)} < lat < {round(y0,6)}\n"
        errstr += f"        {round(x0,6)} < lon < {round(x1,6)}\n"
        sys.exit(errstr)

    if alt is None:
        alt = getAltFromLatLon(lat, lon, xParams, yParams, elevationData)
        if alt is None:
            errstr = "FATAL ERROR: could not determine your altitude!"
            sys.exit(errstr)
        alt = decimal.Decimal(float(alt))

        warnStr = '\033[1;31;m' #ANSI escape sequence, bold and red
        warnStr += "WARNING: you did not input your current altitude\n"
        warnStr += f"    using value {alt}m according to nearest GeoTIFF DEM datapoint\n"
        warnStr += "    your GPS reading may be more accurate than this value"
        warnStr +="\033[0;0m" #ANSI escape sequence, reset terminal to normal colors
        warnStr +="\n"
        print(warnStr)

    if directory is None:
        directory = os.getcwd()

    # used as a priority stack, newest dateTime popped first
    targets_queued = []
    files_queued = []
    files_prosecuted = []

    while True: # only break if list is empty after file walk
        files_queued = []
        for aTuple in targets_queued:
            files_queued.append(aTuple[1])

        for root, dirs, files in os.walk(directory):
            for aFile in files:
                ext = aFile.split('.')[-1].lower()
                if ext != 'jpg': # and ext != 'dng': # DNG raws not supported at this time
                    continue
                elif aFile in files_prosecuted or aFile in files_queued:
                    continue
                else:
                    #from stackoverflow.com/a/14637315
                    #    if XMP in image is spread in multiple pieces, this
                    #    approach will fail to extract data in all
                    #    but the first XMP piece of image
                    fd = open(aFile, 'rb') #read as binary
                    d = str(fd.read()) # ...but convert to string
                    xmp_start = d.find('<x:xmpmeta')
                    xmp_end = d.find('</x:xmpmeta')
                    xmp_str = d[xmp_start:xmp_end+12]
                    fd.close()

                    exifData = {}
                    img = Image.open(aFile)
                    exifDataRaw = img._getexif()
                    if exifDataRaw is None or (xmp_start == xmp_end):
                        print(f'{aFile} - no usable metadata detected, skipping...')
                        files_prosecuted.append(aFile)
                        continue
                    for tag, value in exifDataRaw.items():
                        decodedTag = ExifTags.TAGS.get(tag, tag)
                        exifData[decodedTag] = value
                    make = exifData["Make"].upper()
                    make = make.strip()
                    dateTime = exifData["DateTime"]
                    model = exifData["Model"].upper()
                    model = model.strip()
                    if make[-1] == "\0":
                        # fix nul terminated string bug
                        make = make.rstrip("\0")


                    print(aFile)

                    if make == "DJI":
                        sensData = parseImage.handleDJI(xmp_str)
                        if sensData is not None:
                            y, x, z, azimuth, theta = sensData
                            target = resolveTarget(y, x, z, azimuth, theta, elevationData, xParams, yParams)
                        else:
                            print(f'ERROR with {aFile}, couldn\'t find sensor data', file=sys.stderr)
                            print(f'skipping {aFile}', file=sys.stderr)
                            files_prosecuted.append(aFile)
                            continue
                    elif make == "SKYDIO":
                        sensData = parseImage.handleSKYDIO(xmp_str)
                        if sensData is not None:
                            y, x, z, azimuth, theta = sensData
                            target = resolveTarget(y, x, z, azimuth, theta, elevationData, xParams, yParams)
                        else:
                            print(f'ERROR with {aFile}, couldn\'t find sensor data', file=sys.stderr)
                            print(f'skipping {aFile}', file=sys.stderr)
                            files_prosecuted.append(aFile)
                            continue
                    elif make == "AUTEL ROBOTICS":
                        sensData = parseImage.handleAUTEL(xmp_str, exifData)
                        if sensData is not None:
                            y, x, z, azimuth, theta = sensData
                            target = resolveTarget(y, x, z, azimuth, theta, elevationData, xParams, yParams)
                        else:
                            print(f'ERROR with {aFile}, couldn\'t find sensor data', file=sys.stderr)
                            print(f'skipping {aFile}', file=sys.stderr)
                            files_prosecuted.append(aFile)
                            continue
                    elif make == "PARROT":
                        # will whitelist more models as they are tested
                        if model == "ANAFI":
                            sensData = parseImage.handlePARROT(xmp_str, exifData)
                            if sensData is not None:
                                y, x, z, azimuth, theta = sensData
                                target = resolveTarget(y, x, z, azimuth, theta, elevationData, xParams, yParams)
                            else:
                                print(f'ERROR with {aFile}, couldn\'t find sensor data', file=sys.stderr)
                                print(f'skipping {aFile}', file=sys.stderr)
                                files_prosecuted.append(aFile)
                                continue
                        else:
                            # for instance, the parrot disco fixed-wing doesn't
                            #     have a camera gimbal
                            print(f'ERROR with {aFile}, Parrot {model} is not supported', file=sys.stderr)
                            print(f'skipping {aFile}', file=sys.stderr)
                            files_prosecuted.append(aFile)
                            continue

                    else:
                        print(f'ERROR with {aFile}, make {make} not compatible with this program!', file=sys.stderr)
                        print(f'skipping {aFile}', file=sys.stderr)
                        continue

                    if target is not None:
                        item = (dateTime, aFile, target)
                        targets_queued.append(item)
                    else:
                        files_prosecuted.append(aFile)
        #} end file walk for loop

        if not targets_queued:
            break # break out of 'while True' loop if no more targets
        else:
            targets_queued.sort() # first tuple item is dateTime, so is sorted lexigraphic (and chronologic) order
            this = targets_queued.pop() # get newest image available after each walk
            dateTime, imgName = this[0], this[1]
            print("\n")
            print(imgName)
            print(dateTime)

            tarY, tarX, tarZ = this[2][1], this[2][2], this[2][3]
            brng = haversine_bearing(lon, lat, tarX, tarY)
            print(f"{'Magnetic Bearing' if mag != 0.0 else 'Bearing'}: {round(brng + mag,2)}" + "°" + f" {'(' + ('+' if mag > 0 else '') + str(mag)+'°)' if mag != 0.0 else ''}")
            rangeToTarget = haversine(lon, lat, tarX, tarY, alt)
            print(f"Range: {round(rangeToTarget)}")

            files_prosecuted.append(this[1])

    #} end while True loop

if __name__ == "__main__":
    find_me_mode()