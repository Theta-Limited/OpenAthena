# Fetch GeoTIFF file from internet
From python elevation API's [read the docs](http://elevation.bopen.eu/en/stable/quickstart.html#command-line-usage)

## Install
clipping GeoTIFF files requires the python `elevation` package

This can be installed on most systems with the command `pip install elevation`, or alternatively `pip3 install elevation`


## Command line usage

The `eio clip` command may take a while to complete. This is normal.

Identify the geographic bounds of the area of interest and fetch the DEM with the eio command. For example to clip the SRTM 30m DEM of Rome, around 41.9N 12.5E, to the Rome-30m-DEM.tif file:

The `--bounds` option accepts latitude and longitude coordinates (more precisely in geodetic coordinates in the WGS84 refernce system EPSG:4326 for those who care) given as **`left bottom right top`** similarly to the `rio` command form `rasterio`.

    $ eio clip -o Rome-30m-DEM.tif --bounds 12.35 41.8 12.65 42

In the preceeding example, `12.35` is the western longitude bound, `41.8` is the southern latitude bound, `12.65` is the eastern most longitude bound, and `42` is the northernmost latitude bound of the rectangular area of the desired GeoTIFF file.

To clean up stale temporary files and fix the cache in the event of a server error use:

    $ eio clean

## Aditional notes:
The downloaded elevation data is stored in the [GeoTIFF](https://en.wikipedia.org/wiki/GeoTIFF) file format, which performs efficient, lossless compression. Large areas can be downloaded for later use by OpenAthena offline, all while requiring very little disk space


The excellent elevation data set is generated by a technique known as [Synthetic Aperature Radar](https://www.economist.com/technology-quarterly/2022/01/27/synthetic-aperture-radar-is-making-the-earths-surface-watchable-24/7), which is becoming exceedingly effective and common as a military and GEOint data gathering tool. One advantage of this technique is that radar wavelengths are long enough to pass through some cloud cover and surface foilage before bouncing off of hard surfaces such as metal, buildings, and terrain.


The dataset for the elevation API backing the `eio clip` was generated by the (Space) [Shuttle Radar Topography Mission](https://en.wikipedia.org/wiki/Shuttle_Radar_Topography_Mission#Highest_Resolution_Global_Release) conducted in the year 2000. In 2015 a high resolution global [digital elevation model](https://en.wikipedia.org/wiki/Digital_elevation_model), derived from the SRTM dataset, covering most of the world was released to the public without restriction. This DEM derived from the SRTM mission has a high resolution of 1-arc second (approx 30 meters). [Studies](https://www.sciencedirect.com/science/article/pii/S2090447917300084) have shown the vertical accuracy of the datapoints are very good, with error being observed to be within +/- 10 meters, despite the +/- 16 meters figure which was published in the SRTM data specification

## Improvement
OpenAthena can accept DEM GeoTIFF files of higher resolution or accuracy than the SRTM dataset, if provided by the user. Newer synthetic aperature radar datasets and LIDAR datasests are likely availible to those with significant resources