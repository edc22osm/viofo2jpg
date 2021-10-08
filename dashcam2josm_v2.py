# 
# dashcam2josm_v2.py
# Version: 2021-09-22
# License: GPL3 
#
#
# dashcam2josm_v2.py is based on dashcam2josm.sh script from https://retiredtechie.fitchfamily.org/2018/05/13/dashcam-openstreetmap-mapping/
#
# 
# This script generates geotaged jpg images from .MP4 video file recorded by Viofo dashcam
# 
# Tested on files from  Viofo A129 DUO dashcam (Novatek NTK96663 chip) (front and rear cams) and Mapillary script uploader.
#
# This script requires: 
#    - nvtk_mp42gpx_v2.py script
#    - ffmpeg tool (tested on version git-2020-07-13-7772666 from https://ffmpeg.org)
#    - exiftool tool (tested on version 12.01 from https://exiftool.org)
# 
# Tested on Linux and Windows 10
#
#
# Options:
#
# -i    input .MP4 video file(s), globs (eg: *) or directory(ies)
# 
# -c    Crop images generated from all video files. Format: width:height:x:y
# -cf   Crop images generated from front video files. (For *F.MP4 files.) Format: width:height:x:y
# -cr   Crop images generated from rear video files. (For *R.MP4 files.) Format: width:height:x:y
# This options are useful if you don't want to share your sensitive data saved in the video by dashcam, or if your view is partially obscured.
# Caution: width can not be a multiply of height. It causes bugs in Mapillary. See: https://forum.mapillary.com/t/bug-report-i-uploaded-this-normal-pic-but-it-is-showed-as-an-360/2948/7
#
# -f    Do not skip frames not far enaugh (5m) from previous saved
# By default this script skips images with are too close (less than 5 meters) from previous saved image. 
# This avoid generating many images from same position (in a traffic jam or at traffic lights)
#
# -df   User provided directory with ffmpeg tool.
#
# -de   User provided directory with exiftool tool.
#
#
#
#
# Cautions:
#
# Output files (.jpg files and one .gpx file) are created to subdirectory named like .MP4 source file
# 
# Images are generated every one second during video, but only if gps position is known.
#
# Images generated by rear cam (*R.MP4 files.) has bearing corrected by 180 degrees and moved 2 meters behind.
# It is usefull at Mapillary app for separate two identical tracks (one from front and one from rear dashcam)
# (Remember to upload front and back series of images as separate Mapillary tracks.) 
#
#
#
#
# Oryginal dashcam2josm.sh script description:
#
# Author: Tod Fitch (tod at fitchfamily dot org)
# License: GPL3
# Warranty: NONE! Use at your own risk!
# Disclaimer: Quick and dirty hack.
# Description: This script extract geo referenced images from
#              Novatek generated MP4 files.
#
#   Uses a python script to extract GPS data from the Viofo A119
#   Script is available at:
#       https://sergei.nz/extracting-gps-data-from-viofo-a119-and-other-novatek-powered-cameras/
#
#   Also uses ffmpeg and exiftool.
#
# Output is to a subdirectory with a name based on the base file name for
# the video file.
#


import os, sys, argparse, glob, shutil, subprocess, datetime, calendar, locale
import xml.etree.ElementTree as ET


# bearing correction for images from rear camera [deg] (*R.MP4 files)
bearingCorrectionForRearCam = '180'


filesCount=0;
def check_in_file(in_file):
    in_files=[]
    for f in in_file:
        # glob needed if for some reason quoted glob is passed, or script is run on the most popular proprietary inferior OS
        for f1 in glob.glob(f):
                if os.path.isdir(f1):
                    print("Skipping subdirectory '%s'" % f1)
                elif os.path.isfile(f1):
                    if f1.upper().endswith(".MP4"):
                        print("Queueing file '%s' for processing..." % f1)
                        in_files.append(f1)
                    else:
                        print("File %s omitted. File name must end with .MP4" % f1)
                else:
                    # Catch all for typos...
                    print("Skipping invalid input '%s'..." % f1)
    global filesCount
    filesCount = len(in_files)
    print("Queueing total: '%s' files" % filesCount)
    return in_files


def get_args():
    p = argparse.ArgumentParser(description='This script will attempt to extract geotaged images and GPS data from Novatek MP4 video files')
    p.add_argument('-i',metavar='input',nargs='+',help='input file(s), globs (eg: *) or directory(ies)')
    p.add_argument('-c',metavar='crop',help='Crop images generated from video files. Format: width:height:x:y')
    p.add_argument('-cf',metavar='cropFront',help='Crop images generated from front video file. Format: width:height:x:y')
    p.add_argument('-cr',metavar='cropRear',help='Crop images generated from rear video file. Format: width:height:x:y')
    p.add_argument('-f',action='store_true',help='Do not skip frames not far enaugh (5m) from previous saved')
    p.add_argument('-df',metavar='ffmpegUserDir',help='User provided directory with ffmpeg tool. https://ffmpeg.org')
    p.add_argument('-de',metavar='exiftoolUserDir',help='User provided directory with exiftool tool. https://exiftool.org')
    args=p.parse_args(sys.argv[1:])
    crop=check_crop("c",args.c)
    cropFront=check_crop("cf",args.cf)
    cropRear=check_crop("cr",args.cr)
    ffmpegUserDir=args.df
    exiftoolUserDir=args.de
    try:
        doNotSkip=args.f
        in_file=check_in_file(args.i)
    except:
        print("Unexpected error:", sys.exc_info()[0])
        p.print_help()
        sys.exit(1)
    return (in_file,crop,cropFront,cropRear,doNotSkip,ffmpegUserDir,exiftoolUserDir)


def check_crop(cropParam, cropStr):
    if (not cropStr):
        return cropStr
    cropStrList = cropStr.split(":")
    if (len(cropStrList) != 4):
        print_error("Wrong format of crop (-" + cropParam + ") parameter - reqired format: width:height:x:y")
        sys.exit(1)
    w = cropStrList[0]
    h = cropStrList[1]
    x = cropStrList[2]
    y = cropStrList[3]
    if (not w.isdigit()):
        print_error("First part (width) of crop (-" + cropParam + ") parameter must be positive number")
        sys.exit(1)
    if (not h.isdigit()):
        print_error("Second part (height) of crop (-" + cropParam + ") parameter must be positive number")
        sys.exit(1)
    if (not x.isdigit()):
        print_error("Third part (x) of crop (-" + cropParam + ") parameter must be positive number")
        sys.exit(1)
    if (not y.isdigit()):
        print_error("Fourth part (y) of crop (-" + cropParam + ") parameter must be positive number")
        sys.exit(1)
    if ((int(w)-int(x))%(int(h)-int(y)) == 0):
        print_error("In parameter -" + cropParam + " (Output images size), width is exactly multiply of height. It couses bugs in Mapillary. Please change this size. See: https://forum.mapillary.com/t/bug-report-i-uploaded-this-normal-pic-but-it-is-showed-as-an-360/2948/7")
        sys.exit(1)
    return cropStr


def print_error(errorStr):
    print("===============================")
    print("ERROR:")
    print("%s" % errorStr)
    print("===============================")
    return


def create_subDir(subDirPath,subDirGpx,subDirMp4,sourceMp4):
    if not os.path.isdir(subDirPath):
        os.mkdir(subDirPath)
    # remove *.jpg name.MP4 and name.gpx files from subdirectory
    subDirJpgs = glob.glob(subDirPath+'/*.jpg')
    for subDirJpg in subDirJpgs:
        print("File %s removed." % subDirJpg)
        os.remove(subDirJpg)
    if os.path.exists(subDirGpx):
        os.remove(subDirGpx)
    if os.path.exists(subDirMp4):
        os.remove(subDirMp4)
    # copy source MP4 to subdir
    shutil.copy(sourceMp4, subDirPath)
    return


def create_gpx(name,subDirMp4,currentScriptDir):
    # run nvtk_mp42gpx_v2.py script
    print("START run script. %s " % os.path.join(currentScriptDir,'nvtk_mp42gpx_v2.py'))
    if name.upper().endswith("R"): # *R.MP4 files from rear camera (course rotated 180 deg and gps position moved 2m behind)
        process = subprocess.Popen(['python', os.path.join(currentScriptDir,'nvtk_mp42gpx_v2.py'), '-i', subDirMp4, '-f', '-m', '-b', bearingCorrectionForRearCam], universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    else:                          # *F.MP4 files from front camera
        process = subprocess.Popen(['python', os.path.join(currentScriptDir,'nvtk_mp42gpx_v2.py'), '-i', subDirMp4, '-f', '-m'], universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    for line in iter(process.stdout.readline, ""):
        sys.stdout.write(" >" + line)
        sys.stdout.flush()
    process.wait()
    exitCode = process.returncode
    print("END run script. out = %s" % exitCode)
    return


def utc_to_local(utc_dt):
    # get integer timestamp to avoid precision lost
    timestamp = calendar.timegm(utc_dt.timetuple())
    local_dt = datetime.datetime.fromtimestamp(timestamp)
    assert utc_dt.resolution >= datetime.timedelta(microseconds=1)
    return local_dt.replace(microsecond=utc_dt.microsecond)


def create_jpgs(subDirPath,subDirGpx,name,subDirMp4,fileNum,crop,cropFront,cropRear,doNotSkip,ffmpegDir,exiftoolDir):
    global filesCount
    # read .gpx xml file
    gpxXmlTree = ET.parse(subDirGpx)
    gpxXmlRoot = gpxXmlTree.getroot()
    n=0
    timestampPattern = '%Y-%m-%dT%H:%M:%SZ'
    gpxTrkptElemList = gpxXmlRoot.findall('.//{http://www.topografix.com/GPX/1/0}trkpt')
    s=len(gpxTrkptElemList)
    for gpxTrkptElem in gpxTrkptElemList:
        n=n+1
        paddedNumber='{0:04d}'.format(n)
        gpxDesc = gpxTrkptElem.find('{http://www.topografix.com/GPX/1/0}desc').text
        gpxUtcTimeString = gpxTrkptElem.find('{http://www.topografix.com/GPX/1/0}time').text
        gpxUtcTimeTs = datetime.datetime.strptime(gpxUtcTimeString, timestampPattern)
        gpxSystemTimeTs = utc_to_local(gpxUtcTimeTs)
        gpxUtcTimeString2 = gpxUtcTimeTs.strftime("%Y:%m:%d %H:%M:%S")
        gpxSystemTimeString2 = gpxSystemTimeTs.strftime("%Y:%m:%d %H:%M:%S")
        if n==1:
            firstGpxTimeTs = gpxUtcTimeTs
        if gpxDesc:
            gpxDescList=gpxDesc.split(";")
            frameTimePosition = gpxDescList[0][len("frameTimePosition="):]
            gpxFrameIsFarEnough = gpxDescList[1][len("frameIsFarEnough="):]
        else:
            frameTimePosition = gpxUtcTimeTs - firstGpxTimeTs
            gpxFrameIsFarEnough = "Y"
        subDirNewJpg = os.path.join(subDirPath, name+'_'+paddedNumber+'.jpg')
        if gpxFrameIsFarEnough=="N" and not doNotSkip:
            print('%s/%s:%s/%s: Do not generate .jpg file: at TimeUtc=%s TimeSystem=%s ss=%s. Frame gps location is too close from previous saved frame.'  % (fileNum, filesCount, n, s, gpxUtcTimeString2, gpxSystemTimeString2, frameTimePosition))
            continue
        print('%s/%s:%s/%s: Generate .jpg file: at TimeUtc=%s TimeSystem=%s ss=%s -> %s'  % (fileNum, filesCount, n, s, gpxUtcTimeString2, gpxSystemTimeString2, frameTimePosition, subDirNewJpg))
        os.chdir(ffmpegDir)
        if crop:
            subprocess.call(['ffmpeg', '-loglevel', 'error', '-ss', str(frameTimePosition), '-i', subDirMp4, '-filter:v', 'crop='+crop, '-frames:v', '1', '-qscale:v', '1', subDirNewJpg])
        elif cropRear and name.upper().endswith("R"):
            subprocess.call(['ffmpeg', '-loglevel', 'error', '-ss', str(frameTimePosition), '-i', subDirMp4, '-filter:v', 'crop='+cropRear, '-frames:v', '1', '-qscale:v', '1', subDirNewJpg])
        elif cropFront and not name.upper().endswith("R"):
            subprocess.call(['ffmpeg', '-loglevel', 'error', '-ss', str(frameTimePosition), '-i', subDirMp4, '-filter:v', 'crop='+cropFront, '-frames:v', '1', '-qscale:v', '1', subDirNewJpg])
        else:
            subprocess.call(['ffmpeg', '-loglevel', 'error', '-ss', str(frameTimePosition), '-i', subDirMp4, '-frames:v', '1', '-qscale:v', '1', subDirNewJpg])
        os.chdir(exiftoolDir)
        subprocess.call(['exiftool', '-charset', 'FileName='+locale.getpreferredencoding(), '-CreateDate="'+gpxUtcTimeString2+'"', '-DateTimeOriginal="'+gpxUtcTimeString2+'"', '-FileModifyDate="'+gpxSystemTimeString2+'"', subDirNewJpg]) 
    return


def geotag_jpgs(subDirPath,subDirGpx,name,exiftoolDir):
    print("START exiftool -geotag")
    os.chdir(exiftoolDir)
    # use FileModifyDate saved assuming UTC datetime
    # -geotag option writes exif data: GPS:GPSLatitude, GPS:GPSLongitude, GPS:GPSImgDirection (course)
    subprocess.call(['exiftool', '-charset', 'FileName='+locale.getpreferredencoding(), '-geotag', subDirGpx, '-Geotime<FileModifyDate', '-P', subDirPath])
    print("END exiftool -geotag")
    return


def clean_subDirMp4(subDirMp4):
    os.remove(subDirMp4)
    return

def clean_subDirOrginal(subDirPath):
    subDirExiftoolTmps = glob.glob(subDirPath+'/*original')
    for subDirExiftoolTmp in subDirExiftoolTmps:
        os.remove(subDirExiftoolTmp)
    return

def findToolDir(userDir,toolName,currentScriptDir):
    print("findToolDir: userDir = %s   toolName = %s   currentScriptDir = %s" % (userDir,toolName,currentScriptDir))
    if (userDir and (os.path.exists(os.path.join(userDir,toolName)) or os.path.exists(os.path.join(userDir,toolName+'.exe')))):
        #print("user provided directory contains tool file")
        return userDir
    if (os.path.exists(os.path.join(os.path.join(currentScriptDir,toolName),toolName)) or os.path.exists(os.path.join(os.path.join(currentScriptDir,toolName),toolName+'.exe'))):
        #print("directory currentScriptDir\\toolName contains tool file")
        return os.path.join(currentScriptDir,toolName)
    #print("return currentScriptDir with hope that tool is on the system path")
    return currentScriptDir

def main():
    startTs = datetime.datetime.now()
    in_files,crop,cropFront,cropRear,doNotSkip,ffmpegUserDir,exiftoolUserDir=get_args()
    orginalDir=os.getcwd()
    currentScriptDir = os.path.dirname(os.path.realpath(__file__))
    ffmpegDir=findToolDir(ffmpegUserDir,'ffmpeg',currentScriptDir)
    exiftoolDir=findToolDir(exiftoolUserDir,'exiftool',currentScriptDir)
    print("currentScript = %s   currentScriptDir = %s   currentDirectory = %s   ffmpegDir = %s   exiftoolDir = %s   systemencoding = %s" % (os.path.realpath(__file__),currentScriptDir,os.getcwd(),ffmpegDir,exiftoolDir,locale.getpreferredencoding()))
    print('current video file/total video files:current frame/total video frames:')
    fileNum=0
    for f in in_files:
        fileNum=fileNum+1
        name = f[0:len(f)-4]
        sourceMp4=os.path.join(os.getcwd(),f)
        # make subdir for each .MP4 file
        subDirPath=os.path.join(os.getcwd(),name)
        subDirGpx = os.path.join(subDirPath, name+'.gpx')
        subDirMp4 = os.path.join(subDirPath, name+'.MP4')
        print("f=%s name=%s subDirPath=%s" % (f, name, subDirPath))
        # prepare subfolder for source MP4 file
        create_subDir(subDirPath,subDirGpx,subDirMp4,sourceMp4)
        # create .gpx file from source MP4 via nvtk_mp42gpx.py script
        create_gpx(name,subDirMp4,currentScriptDir)
        # create .jpg files from source MP4 via ffmpeg and exiftool
        create_jpgs(subDirPath,subDirGpx,name,subDirMp4,fileNum, crop,cropFront,cropRear,doNotSkip,ffmpegDir,exiftoolDir)
        # remove tmp *.MP4 files
        clean_subDirMp4(subDirMp4)
        # geotag .jpg files from .gpx file via exiftool
        geotag_jpgs(subDirPath,subDirGpx,name,exiftoolDir)
        # remove tmp *.original files
        clean_subDirOrginal(subDirPath)
        os.chdir(orginalDir)
    endTs = datetime.datetime.now()
    print("")
    print("Script completed. Time=%s" % (endTs-startTs))
    return

if __name__ == "__main__":
    main()
