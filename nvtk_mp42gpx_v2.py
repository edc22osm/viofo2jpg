# 
# nvtk_mp42gpx_v2.py
# Version: 2021-09-22
# License: GPL3 
#
#
# nvtk_mp42gpx_v2.py is based on nvtk_mp42gpx.py script from https://sergei.nz/2020-update-of-the-nvtk_mp42gpx-py-script/
#
#
# Script extracts GPS data from Novatek generated MP4 files.
# 
# Options
# 
# -i    input file(s), globs (eg: *) or directory(ies)
# -o    output file (single .gpx file with track at "http://www.topografix.com/GPX/1/0" format)
# -f    overwrite output file if exists
# -d    deobfuscates coordinates, if the file only works with JMSPlayer use this flag
# -m    multiple output files (default creates a single output file). Note: files will be named after originals.
# 
# 
# New feauters:
#
# New option:  -b   Bearing correction [degrees]
# For example if you have video from rear dashcam mounted to film the back.
# 
# New option:  -c   Do not distance same gps positions if bearing correction. 
# By default, if "-b 180" used, frames will be distanced 2m back.
# It is usefull at Mapillary app for separate two identical tracks (one from front and one from rear dashcam)
# -c option will disable this behavior.
# 
# New fields at .gpx output file used in dashcam2josm_v2.py script:
# frameTimePosition - Frame time in video file. If GPS data begins after video (after gps fix time) real frame position at video is saved here. (trkpt for frames without GPS data are not saved to .gpx file.)
# frameIsFarEnough - "Y" if the distance from the previous frame (trkpt) is more than 5 meters, "N" otherwise 
# 
# Fixed unicode video file names saved to .gpx output file
# 
# 
# 
# Oryginal nvtk_mp42gpx.py script description:
#
# Author: Sergei Franco (sergei at sergei.nz)
# License: GPL3 
# Warranty: NONE! Use at your own risk!
# Disclaimer: I am no programmer!
# Description: this script will crudely extract embedded GPS data from Novatek generated MP4 files.

import os, struct, sys, argparse, glob, math, datetime
if sys.version_info.major > 2:  # Python 3 or later
    from urllib.parse import quote
else:  # Python 2
    from urllib import quote

gpx = ''
in_file = ''
out_file = ''
deobfuscate = False
bearingCorrection = 0;

def check_out_file(out_file,force):
    if os.path.isfile(out_file) and not force:
        print("Warning: specified out file '%s' exists, specify '-f' to overwrite it!" % out_file)
        return False
    return True

        
def check_in_file(in_file):
    in_files=[]
    for f in in_file:
        # glob needed if for some reason quoted glob is passed, or script is run on the most popular proprietary inferior OS
        for f1 in glob.glob(f):
                if os.path.isdir(f1):
                    print("Directory '%s' specified as input, listing..." % f1)
                    for f2 in os.listdir(f1):
                        f3 = os.path.join(f1,f2)
                        if os.path.isfile(f3):
                            print("Queueing file '%s' for processing..." % f3)
                            in_files.append(f3)
                elif os.path.isfile(f1):
                    print("Queueing file '%s' for processing..." % f1)
                    in_files.append(f1)
                else:
                    # Catch all for typos...
                    print("Skipping invalid input '%s'..." % f1)
    return in_files


def get_args():
    p = argparse.ArgumentParser(description='This script will attempt to extract GPS data from Novatek MP4 file and output it in GPX format')
    p.add_argument('-i',metavar='input',nargs='+',help='input file(s), globs (eg: *) or directory(ies)')
    p.add_argument('-o',metavar='output',nargs=1,help='output file (single)')
    p.add_argument('-f',action='store_true',help='overwrite output file if exists')
    p.add_argument('-d',action='store_true',help='deobfuscates coordinates, if the file only works with JMSPlayer use this flag')
    p.add_argument('-m',action='store_true',help='multiple output files (default creates a single output file). Note: files will be named after originals.')
    p.add_argument('-b',type=int,default=0,help='Bearing correction [degrees]')
    p.add_argument('-c',action='store_true',help='Do not distance same gps positions if bearing correction. (by default, if "-b 180" used, frames from rear camera (*R.MP4) will be distanced 2m back)')
    try:
        args=p.parse_args(sys.argv[1:])
        force=args.f
        if args.o and args.m:
            print("Warning: '-m' is set: output file name will be derived from input file name, '-o' will be ignored")
        if not args.m:
            out_file=args.o[0]
            if not check_out_file(out_file,force):
                sys.exit(1)
        else:
            out_file=None
        multiple=args.m
        deobfuscate=args.d
        in_file=check_in_file(args.i)
        bearingCorrection=args.b
        doNotBearingDistance=args.c
    except:
        p.print_help()
        sys.exit(1)
    return (in_file,out_file,force,multiple,bearingCorrection,doNotBearingDistance)


def fix_coordinates(hemisphere,coordinate):
    # Novatek stores coordinates in odd DDDmm.mmmm format
    if not deobfuscate:
        minutes = coordinate % 100.0
        degrees = coordinate - minutes
        coordinate = degrees / 100.0 + (minutes / 60.0)
    if hemisphere == 'S' or hemisphere == 'W':
        return -1*float(coordinate)
    else:
        return float(coordinate)


#[knot] -> [m/s]
def fix_speed(speed):
    # 1 knot = 0.514444 m/s
    return speed * float(0.514444)


def correct_bearing(bearing,bearingCorrection):
    return (bearing+bearingCorrection)%360


R = 6378.1 #Radius of the Earth [km]
d = 0.001 #Distance in [km] (1m)
def distance_position_if_bearingCorrection(lat1,lon1,bearing,bearingCorrection):
    # mapillary interface (web or josm plugin) has problem with more then one image with same lat,lon and different bearing 
    # (situation when we has one file from front dashcam and second file from rear dashcam with produces track points with same lat,lon and different bearing)
    # to fix this problem, distance points from files with defined bearingCorrection != 0
    # see: https://stackoverflow.com/questions/7222382/get-lat-long-given-current-point-distance-and-bearing
    if bearingCorrection == 0:
        return (lat1,lon1)
    # first, calculate position 1[m] behind oryginal and save as center position
    bearing2 = (bearing+180) % 360
    lat1rad = math.radians(lat1) #Oryginal lat point converted to radians
    lon1rad = math.radians(lon1) #Oryginal long point converted to radians
    lat2rad = math.asin( math.sin(lat1rad)*math.cos(d/R) + math.cos(lat1rad)*math.sin(d/R)*math.cos(math.radians(bearing2)))
    lon2rad = lon1rad + math.atan2(math.sin(math.radians(bearing2))*math.sin(d/R)*math.cos(lat1rad),math.cos(d/R)-math.sin(lat1rad)*math.sin(lat2rad))
    # second, calculate position 1[m] from center position with direction equals to bearingCorrection
    # (for rear dashcam with bearingCorrection=180[deg] we have got 2[m] distance behind oryginal point)
    bearing3 = (bearing+bearingCorrection) % 360
    lat3rad = math.asin(math.sin(lat2rad)*math.cos(d/R) + math.cos(lat2rad)*math.sin(d/R)*math.cos(math.radians(bearing3)))
    lon3rad = lon2rad + math.atan2(math.sin(math.radians(bearing3))*math.sin(d/R)*math.cos(lat2rad),math.cos(d/R)-math.sin(lat2rad)*math.sin(lat3rad))
    lat3 = math.degrees(lat3rad)
    lon3 = math.degrees(lon3rad)
    #print("bearing=%s bearing2=%s bearing3=%s  lat1=%s lon1=%s  lat2=%s lon2=%s  lat3=%s lon3=%s" % (bearing,bearing2,bearing3,lat1,lon1,math.degrees(lat2rad),math.degrees(lon2rad),lat3,lon3))
    return (lat3,lon3)


previousLatitude = 0
previousLongitude = 0
minimalDistance = 0.005 #[km]
def isFrameFarEnoughFromPrevious(latitude,longitude):
    global previousLatitude
    global previousLongitude
    if previousLatitude == 0:
        previousLatitude = latitude
        previousLongitude = longitude
        return "Y"
    else:
        lat1 = math.radians(previousLatitude)
        lon1 = math.radians(previousLongitude)
        lat2 = math.radians(latitude)
        lon2 = math.radians(longitude)
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance = R * c
        if distance > minimalDistance:
            previousLatitude = latitude
            previousLongitude = longitude
            return "Y"
        else:
            return "N"
    
    
def get_atom_info(eight_bytes):
    try:
        atom_size,atom_type=struct.unpack('>I4s',eight_bytes)
    except struct.error:
        return 0,''
    try:
        a_t = atom_type.decode()
    except UnicodeDecodeError:
        a_t = 'UNKNOWN'
    return int(atom_size),a_t


def get_gps_atom_info(eight_bytes):
    atom_pos,atom_size=struct.unpack('>II',eight_bytes)
    return int(atom_pos),int(atom_size)


videoStartTs = None
videoStartTsInfo = ""
videoStartWrongAtoms = 0
def get_gps_atom(gps_atom_info,f,bearingCorrection,doNotBearingDistance):
    global videoStartTs
    global videoStartTsInfo
    global videoStartWrongAtoms
    atom_pos,atom_size=gps_atom_info
    #print("get_gps_atom:  atom_pos=%d atom_size=%d" % (atom_pos,atom_size))
    if atom_size == 0 or atom_pos == 0:
        return
    f.seek(atom_pos)
    data=f.read(atom_size)
    expected_type='free'
    expected_magic='GPS '
    atom_size1,atom_type,magic=struct.unpack_from('>I4s4s',data)
    try:
        atom_type=atom_type.decode()
        magic=magic.decode()
        #sanity:
        if atom_size != atom_size1 or atom_type != expected_type or magic != expected_magic:
            print("Error! skipping atom at %x (expected size:%d, actual size:%d, expected type:%s, actual type:%s, expected magic:%s, actual maigc:%s)!" % (int(atom_pos),atom_size,atom_size1,expected_type,atom_type,expected_magic,magic))
            return

    except UnicodeDecodeError as e:
        print("Skipping: garbage atom type or magic. Error: %s." % str(e))
        return

    # checking for weird Azdome 0xAA XOR "encrypted" GPS data. This portion is a quick fix.
    if data[12] == '\x05':
        if atom_size < 254:
            payload_size = atom_size
        else:
            payload_size = 254
        payload = []
        # really crude XOR decryptor
        for i in range(payload_size):
            payload.append(chr(struct.unpack_from('>B', data[18+i])[0] ^ 0xAA))

        year = ''.join(payload[8:12])
        month = ''.join(payload[12:14])
        day = ''.join(payload[14:16])
        hour = ''.join(payload[16:18])
        minute = ''.join(payload[18:20])
        second = ''.join(payload[20:22])
        videoCurrentTs = datetime.datetime((year+2000), int(month), int(day), int(hour), int(minute), int(second), 0)
        if videoStartTs is None:
            videoStartTs = videoCurrentTs
        time = videoCurrentTs.strftime("%Y-%m-%dT%H:%M:%SZ")
        frameTimePosition = videoCurrentTs - videoStartTs
        latitude = fix_coordinates(payload[38],float(''.join(payload[39:47]))/10000)
        longitude = fix_coordinates(payload[47],float(''.join(payload[48:56]))/1000)
        #speed is not as accurate as it could be, only -1/+0 km/h accurate.
        speed = float(''.join(payload[57:65]))/3.6
        frameIsFarEnough=isFrameFarEnoughFromPrevious(latitude,longitude)
        #no bearing data
        bearing = 0

    else:
        if atom_size < 56:
            print("Skipping too small atom %d<56." % atom_size)
            return
        # Because for some silly reason different versions of firmware move where the data is in the atom.
        # Start on the begining (optimal when pattern is close to beginning of atom) to look for A{N,S}{E,W} pattern, looking for up to position 20 counting from the end.
        #the beginning of the atom, skipping the atom "metadata".
        beginning=12
        offset=beginning
        while offset < atom_size-20:
            a,lon,lat=struct.unpack_from('<sss',data,offset)
            #print("format offset=%d a=%s lon=%s lat=%s" % (offset,a,lon,lat))
            if a==b'A' and (lon==b'N' or lon==b'S') and (lat==b'E' or lat==b'W'):
                #the A{N,S}{E,W} is 24 bytes away from the beginning of the gps data packet
                offset=offset-24
                #print("Found atom offset=%d" % offset)
                sys.stdout.write(".")
                sys.stdout.flush()
                break
            offset+=1
        else:
            #print("Skipping atom because no data has been found in the expected format")
            sys.stdout.write("x")
            sys.stdout.flush()
            if videoStartTs is None:
                videoStartWrongAtoms = videoStartWrongAtoms + 1
            return
            
        # Added Bearing as per RetiredTechie contribuition: http://retiredtechie.fitchfamily.org/2018/05/13/dashcam-openstreetmap-mapping/
        hour,minute,second,year,month,day,active,latitude_b,longitude_b,_,latitude,longitude,speed,bearing = struct.unpack_from('<IIIIIIssssffff',data, offset)
        try:
            active=active.decode()
            latitude_b=latitude_b.decode()
            longitude_b=longitude_b.decode()

        except UnicodeDecodeError as e:
            print("Skipping: garbage data. Error: %s." % str(e))
            return

        if deobfuscate:
            #print(latitude,longitude)
            # https://sergei.nz/dealing-with-data-obfuscation-in-some-chinese-dash-cameras/
            latitude = (latitude - 187.98217) / 3
            longitude = (longitude - 2199.19876) * 0.5

        # Assume that datetime from mp4 is always UTC time. Ignore timezone setting from device (no data at mp4 about it)
        videoCurrentTs = datetime.datetime((year+2000), int(month), int(day), int(hour), int(minute), int(second), 0)
        videoCurrentTs = videoCurrentTs - datetime.timedelta(0, 1) # device clock is 1 second after its gps data
        if videoStartTs is None:
            videoStartTs = videoCurrentTs - datetime.timedelta(0, videoStartWrongAtoms)
            #print("Video started %s seconds before gps data. At %s." % (str(videoStartWrongAtoms), videoStartTs))
            videoStartTsInfo = "Video stream started at %s - %s seconds before gps data." % (videoStartTs, str(videoStartWrongAtoms))
        time = videoCurrentTs.strftime("%Y-%m-%dT%H:%M:%SZ")
        frameTimePosition = videoCurrentTs - videoStartTs
        #print("videoCurrentTs: %s %s %s" % (videoCurrentTs, frameTimePosition, time))
        latitude=fix_coordinates(latitude_b,latitude)
        longitude=fix_coordinates(longitude_b,longitude)
        speed=fix_speed(speed)
        frameIsFarEnough=isFrameFarEnoughFromPrevious(latitude,longitude)
        if not doNotBearingDistance:
            latitude,longitude=distance_position_if_bearingCorrection(latitude,longitude,bearing,bearingCorrection)
        correctedBearing=correct_bearing(bearing,bearingCorrection)
        #it seems that A indicate reception
        if active != 'A':
            print("Skipping: lost GPS satelite reception. Time: %s." % time)
            return
    #print("Add atom. time=%s" % time)
    return (latitude,longitude,time,correctedBearing,speed,frameTimePosition,frameIsFarEnough)


def get_gpx(gps_data,out_file):
    f_name = os.path.basename(out_file)
    gpx  = '<?xml version="1.0" encoding="UTF-8"?>\n'
    gpx += '<gpx version="1.0"\n'
    gpx += '\tcreator="Sergei\'s Novatek MP4 GPS parser"\n'
    gpx += '\txmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"\n'
    gpx += '\txmlns="http://www.topografix.com/GPX/1/0"\n'
    gpx += '\txsi:schemaLocation="http://www.topografix.com/GPX/1/0 http://www.topografix.com/GPX/1/0/gpx.xsd">\n'
    gpx += "\t<name>%s</name>\n" % quote(f_name)
    gpx += '\t<url>sergei.nz</url>\n'
    gpx += "\t<trk><name>%s</name><trkseg>\n" % quote(f_name)
    for l in gps_data:
        if l:
            gpx += "\t\t<trkpt lat=\"%f\" lon=\"%f\"><time>%s</time><course>%f</course><speed>%f</speed><desc>frameTimePosition=%s;frameIsFarEnough=%s</desc></trkpt>\n" % l
    gpx += '\t</trkseg></trk>\n'
    gpx += '</gpx>\n'
    return gpx


def process_file(in_file,gps_data,bearingCorrection,doNotBearingDistance):
    global videoStartTsInfo
    print("Processing file '%s'..." % in_file)
    with open(in_file, "rb") as f:
        offset = 0
        while True:
            atom_pos = f.tell()
            atom_size, atom_type = get_atom_info(f.read(8))
            if atom_size == 0:
                if len(videoStartTsInfo)>0:
                    print()
                    print(videoStartTsInfo)
                break

            if atom_type == 'moov':
                print("Found moov atom...")
                sub_offset = offset+8

                while sub_offset < (offset + atom_size):
                    #sub_atom_pos = f.tell()
                    sub_atom_size, sub_atom_type = get_atom_info(f.read(8))

                    if str(sub_atom_type) == 'gps ':
                        print("Found gps chunk descriptor atom...")
                        print("Parsing atoms: '.'- with gps data, 'x'-without gps data")
                        gps_offset = 16 + sub_offset # +16 = skip headers
                        f.seek(gps_offset,0)
                        while gps_offset < ( sub_offset + sub_atom_size):
                            gps_data.append(get_gps_atom(get_gps_atom_info(f.read(8)),f,bearingCorrection,doNotBearingDistance))
                            gps_offset += 8
                            f.seek(gps_offset,0)

                    sub_offset += sub_atom_size
                    f.seek(sub_offset,0)

            offset += atom_size
            f.seek(offset,0)


def main():
    in_files,out_file,force,multiple,bearingCorrection,doNotBearingDistance=get_args()
    if multiple:
        for f in in_files:
            f_name,_ = os.path.splitext(f)
            out_file=f_name+'.gpx'
            if not check_out_file(out_file,force):
                continue
            gps_data=[]
            process_file(f,gps_data,bearingCorrection,doNotBearingDistance)
            gpx=get_gpx(gps_data,out_file)
            print("")
            print("Found %d GPS data points in file %s" % (len(gps_data),f_name))
            if gpx:
                with open (out_file, "w") as f:
                    print("Wiriting data to output file '%s'..." % out_file)
                    f.write(gpx)
            else:
                print("GPS data not found...")
    else:
        gps_data=[]
        for f in in_files:
            process_file(f,gps_data,bearingCorrection,doNotBearingDistance)
        gpx=get_gpx(gps_data,out_file)
        print("Found %d GPS data points..." % len(gps_data))
        if gpx:
            with open (out_file, "w") as f:
                print("Wiriting data to output file '%s'..." % out_file)
                f.write(gpx)
        else:
            print("GPS data not found...")
            sys.exit(1)

        print("Success!")

    
if __name__ == "__main__":
    main()
