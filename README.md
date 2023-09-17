# viofo2jpg

Python scripts to generate geotaged images from Viofo A129 DUO (and simillar) dashcam videos. Images are ready to use at e.g Mapillary.com


## Files
dashcam2josm.py - Script generates geotaged jpg images from .MP4 video file recorded by Viofo dashcam
nvtk_mp42gpx.py - Script extracts GPS data from Novatek generated MP4 files.


## Use
```
cd <path_to_your_Viofo_dashcam_MP4_videos>
python <path_to_script>\dashcam2josm.py -i *.MP4
```

Options:
```
-i    input .MP4 video file(s), globs (eg: *) or directory(ies)
-c    Crop images generated from all video files. Format: width:height:x:y
-cf   Crop images generated from front video files. (For *F.MP4 files.) Format: width:height:x:y
-cr   Crop images generated from rear video files. (For *R.MP4 files.) Format: width:height:x:y
      This options are useful if you don't want to share your sensitive data saved in the video by dashcam, or if your view is partially obscured.
-a    Arrange output .jpg files from many input .mp4 files into one output folder per continuous camera sequence
-f    Do not skip frames not far enaugh (5m) from previous saved
      By default this script skips images with are too close (less than 5 meters) from previous saved image. 
-df   User provided directory with ffmpeg tool.
-de   User provided directory with exiftool tool.
```

See scripts for more information 

## Mapillary.com hints

Use [mapillary_tools](https://github.com/mapillary/mapillary_tools) to upload images made from your dashcam movies.
*Upload images from front and rear dashcam as separate tracks !*

cmd

```
cd <path_to_jpgs>
mapillary_tools process_and_upload --import_path . --user_name "mapillary_user_name"
```

Example of uploaded track:
https://www.mapillary.com/app/?lat=50.324699&lng=18.927374&z=17.436678368356983&pKey=614167796256046&focus=photo



## License
GPL3 







