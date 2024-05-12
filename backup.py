from __future__ import print_function
import os, pickle, json, requests, imageio, sys, re, datetime
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.http import MediaIoBaseDownload

# Setup the Photo v1 API
SCOPES = ['https://www.googleapis.com/auth/photoslibrary.readonly']
creds = None

# Check if running on local environment
#is_local_env = os.getenv('IS_LOCAL') == 'true'

if os.path.exists("token.pickle"):
    with open("token.pickle", "rb") as tokenFile:
        print("Loading pickle file")
        creds = pickle.load(tokenFile)
else:
    flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
    creds = flow.run_local_server(port=0)
    with open("token.pickle", "wb") as tokenFile:
        pickle.dump(creds, tokenFile)


if not creds:
    print("No creds found, remove token.pickle file and try again")
    sys.exit(1)
    
# Build the Photos v1 API service
service = build('photoslibrary', 'v1', credentials=creds, static_discovery=False)

def download_all_media(directory, year):
    print(f"Backing up all the media files of year {year} to the folder {directory}")
    # Create the download directory if it doesn't exist
    os.makedirs(directory, exist_ok=True)

    try:
        pageToken=''
        results = service.mediaItems().search(body={'pageSize':100, 'orderBy':'MediaMetadata.creation_time desc', 'filters': {'dateFilter':{'dates': [{'year': year}]}}, 'pageToken':pageToken}).execute()
        pageToken=results.get('nextPageToken')
        media_items = results.get('mediaItems', [])
    except Exception as e:
        print(f"Error retrieving media items: {e}")
        return

    skipped=0
    while media_items is not None:
        # Download each media item
        for media_item in media_items:
            if (skipped>=5):
                print(f"Skipped {skipped} media items, finishing!")
                return
            
            day = media_item['mediaMetadata']['creationTime'][:10]
            folder = directory+'/'+day
            if not os.path.exists(folder):
                os.makedirs(folder)
                print("Folder "+folder+" created.")

            media_item_filename = scapeFilename(media_item['filename'])
            filename = os.path.join(directory, day, media_item_filename+'.json')
            request = service.mediaItems().get(mediaItemId=media_item['id'])

            # Download the media item
            try:
                with open(filename, 'wb') as fh:
                    downloader = MediaIoBaseDownload(fh, request)
                    done = False
                    while not done:
                        status, done = downloader.next_chunk()
                        #print(f'Downloading {filename}: {int(status.progress() * 100)}%')
            except Exception as e:
                print(f"Error downloading {filename}: {e}")
        
            with open(filename) as f:
                data = f.read()
                parsed_data = json.loads(data)
                #print(parsed_data)
                url=parsed_data['baseUrl']
                media_filename = filename.rstrip(".json")
                width=parsed_data['mediaMetadata']['width']
                height=parsed_data['mediaMetadata']['height']
                url=url+sufixByType(media_filename, width, height)
                numDownloads=downloadFile(url, media_filename)
                if (numDownloads==0):
                    skipped=skipped+1
        try:
            if pageToken is None:
                print('No more pages to scan, exiting!')
                return

            results = service.mediaItems().search(body={'pageSize':100, 'orderBy':'MediaMetadata.creation_time desc', 'filters': {'dateFilter':{'dates': [{'year': year}]}}, 'pageToken':pageToken}).execute()
            pageToken=results.get('nextPageToken')
            media_items = results.get('mediaItems', [])
        except Exception as e:
            print(f"Error retrieving media items: {e}")
            return

def scapeFilename(filename):
    specials = r'[/\\?%*:|"<>]'
    scaped = re.sub(specials, '_', filename)
    return scaped

def sufixByType(file_name, width, height):
    file_extension = file_name.lower().split('.')[-1]
    images = ['bmp', 'jpg', 'jpeg', 'gif', 'png', 'heic', 'tiff', 'ico', 'webp', 'pdf']
    videos = ['3gp', 'mmv', '3g2', 'mod', 'asf', 'mov', 'avi', 'mp4', 'divx', 'mpg', 'm2t', 'mts', 'm2ts', 'tod', 'm4v', 'wmv']

    if file_extension in images:
        return '=w'+width+'-h'+height
    elif file_extension in videos:
        return '=dv'
    else:
        raise ValueError(f"Unknown file type in file {file_name}")


def downloadFile(url, destination):
    if os.path.exists(destination):
        print(f'The file {destination} already exists, skipping.')
        return 0
    #print(url)
    print(f'Downloading {destination} media file')
    response = requests.get(url)
    if response.status_code == 200:
        with open(destination, 'wb') as f:
            f.write(response.content)
        convertHeic2JpgIfNeeded(destination)
        return 1
    else:
        print("Error downloading file.")
        return 0

def convertHeic2JpgIfNeeded(filename):
    if filename.endswith('.HEIC'):
        jpg_filename = filename[:-5] + '.jpg'
        print(f"Transforming file .heic {filename} to {jpg_filename}")
        try:
            image = imageio.v2.imread(filename)
            imageio.imwrite(jpg_filename, image)
            print(f"DONE! file {filename} converted to {jpg_filename}")
        except Exception as e:
            print(f"Error converting {filename} to JPG: {e}")

def main(year=None, download_directory='photos'):
    if year is None:
        year = datetime.datetime.now().year
        print(f"Automatically selectiong current year ({year})")
    download_all_media(download_directory, year)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        year = int(sys.argv[1])  # year is the first argument
        if len(sys.argv) > 2:
            if (sys.argv[2]!=None):
                folder=sys.argv[2]
                main(year, folder)
                sys.exit(0)

        main(year)
    else:
        main()