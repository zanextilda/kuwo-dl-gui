import argparse
import requests
import datetime
import json


def main(input_url):
    dump_metadata = True
    keep_album_art = True
    create_album_folder = True

    trackCheck = 'play_detail'
    albumCheck = 'album_detail'

    ID = input_url.split('/')[-1]

    if trackCheck in input_url:
        media_type = 'track'
    elif albumCheck in input_url:
        media_type = 'album'
    else:
        print("Invalid URL. Please provide a URL containing 'play_detail' or 'album_detail'.")
        return

    if media_type == 'track':
        info = ''
        results = ''

        trackInfo = f"https://musicpay.kuwo.cn/music.pay?op=query&action=download&ids={ID}"
        tinfo = requests.get(trackInfo).json()['songs'][0]
        songname = tinfo['name'].replace('(Explicit)', '[E]')
        duration = tinfo['duration']
        duration = f"{int(duration) // 60}:{int(duration) % 60:02}"
        artist = tinfo['artist']
        releaseUnix = tinfo['timingonline']
        dt_object = datetime.datetime.fromtimestamp(int(releaseUnix))
        release = str(dt_object.strftime('%Y-%m-%d'))
        minfo = tinfo['MINFO']
        album = tinfo['album']
        trackNo = '0'
        tid = tinfo['id']
        coverUrl = requests.get(f"https://artistpicserver.kuwo.cn/pic.web?corp=kuwo&type=rid_pic&pictype=250&size=250&rid={tid}").text

        jsonDataFile = {
            "image_url": f"{coverUrl}",
            "songs": []
        }

        entries = minfo.split(';')
        parsed_output = []
        for entry in entries:
            fields = entry.split(',')
            fmt = ''
            bitrate = ''
            size = ''
            
            for field in fields:
                key, value = field.split(':')
                if key == 'format':
                    fmt = value
                elif key == 'bitrate':
                    bitrate = value
                elif key == 'size':
                    size = value.upper()
                    
            parsed_output.append(f"{fmt}_{bitrate}|{size}")

        for line in parsed_output[::-1]:
            codec = line
    
        quality = codec.split('|')[0].split('_')[0]
        bitrate = codec.split('|')[0].split('_')[-1] + 'kbps'
        size = codec.split('|')[1]

        parsedSong = {
            "artist": artist,
            "title": songname,
            "filesize": size,
            "id": tid
        }

        jsonDataFile["songs"].append(parsedSong)

        with open('album_data.json', 'w') as file:
            json.dump(jsonDataFile, file, indent=4)

        print(jsonDataFile)

    elif media_type == 'album':
        print()
        info = ''
        results = ''
        albumInfo = f"https://search.kuwo.cn/r.s?albumid={ID}&stype=albuminfo&pcjson=1"

        ainfo = requests.get(albumInfo).json()

        album = ainfo['name']
        release = ainfo['pub']
        print(f"[{album}] ({release})")
        coverUrl = ainfo['img'].replace('/120/', '/0/').replace('/240/', '/0/').replace('/0/', '/250/')
        
        tracks = ainfo['musiclist']

        jsonDataFile = {
            "image_url": f"{coverUrl}",
            "songs": []
        }

        for track in tracks:
            songname = track['name'].replace('(Explicit)', '')
            artist = track['artist'].replace('&', ', ')
            formats = track['formats'].replace('|AAC48', '')
            bestFormat = formats.split('|')[-1]
            trackNo = track['track']
            tid = track['id']
            minfo = track['MINFO']

            entries = minfo.split(';')
            parsed_output = []
            for entry in entries:
                fields = entry.split(',')
                fmt = ''
                bitrate = ''
                size = ''
                
                for field in fields:
                    key, value = field.split(':')
                    if key == 'format':
                        fmt = value
                    elif key == 'bitrate':
                        bitrate = value
                    elif key == 'size':
                        size = value.upper()
                        
                parsed_output.append(f"{fmt}_{bitrate}|{size}")

            for line in parsed_output[::-1]:
                codec = line

            quality = codec.split('|')[0].split('_')[0]
            bitrate = codec.split('|')[0].split('_')[-1] + 'kbps'
            size = codec.split('|')[1]
              
            parsedSong = {
                "artist": artist,
                "title": songname,
                "filesize": size,
                "id": tid
            }

            jsonDataFile["songs"].append(parsedSong)

        with open('album_data.json', 'w') as file:
            json.dump(jsonDataFile, file, indent=4)

        print(jsonDataFile)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Parse music track or album from a URL.')
    parser.add_argument('inputUrl', type=str, help='The input URL to parse.')

    args = parser.parse_args()
    main(args.inputUrl)
