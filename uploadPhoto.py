from __future__ import print_function
from google_auth_oauthlib.flow import InstalledAppFlow
from apiclient.discovery import build
from httplib2 import Http
from google.auth.transport.requests import AuthorizedSession
import pickle
import json
import logging
import sys
import sh
import os
import glob

def getAlbums(session, appCreatedOnly=False):
    params = {
            'excludeNonAppCreatedData': appCreatedOnly
    }
    while True:
        albums = session.get('https://photoslibrary.googleapis.com/v1/albums', params=params).json()
        logging.debug("Server response: {}".format(albums))
        if 'albums' in albums:
            for a in albums["albums"]:
                yield a
            if 'nextPageToken' in albums:
                params["pageToken"] = albums["nextPageToken"]
            else:
                return
        else:
           return

def create_or_retrieve_album(session, album_title):
# Find albums created by this app to see if one matches album_title
    for a in getAlbums(session, True):
        if a["title"].lower() == album_title.lower():
            album_id = a["id"]
            logging.info("Uploading into EXISTING photo album -- \'{0}\'".format(album_title))
            return album_id
# No matches, create new album
    create_album_body = json.dumps({"album":{"title": album_title}})
    #print(create_album_body)
    resp = session.post('https://photoslibrary.googleapis.com/v1/albums', create_album_body).json()
    logging.debug("Server response: {}".format(resp))
    if "id" in resp:
        logging.info("Uploading into NEW photo album -- \'{0}\'".format(album_title))
        return resp['id']
    else:
        logging.error("Could not find or create photo album '\{0}\'. Server Response: {1}".format(album_title, resp))

def upload_photos(session, photo_file_list, photo_uploaded_list, album_id, album_name):
    session.headers["Content-type"] = "application/octet-stream"
    session.headers["X-Goog-Upload-Protocol"] = "raw"
    for photo_file_name in photo_file_list:
            if photo_file_name+".u" in photo_uploaded_list:
                logging.info("Already uploaded "+photo_file_name);
                continue
            try:
                photo_file = open(photo_file_name, mode='rb')
                photo_bytes = photo_file.read()
            except OSError as err:
                logging.error("Could not read file \'{0}\' -- {1}".format(photo_file_name, err))
                continue
            session.headers["X-Goog-Upload-File-Name"] = os.path.basename(photo_file_name)
            logging.info("Uploading photo -- \'{}\'".format(photo_file_name))
            upload_token = session.post('https://photoslibrary.googleapis.com/v1/uploads', photo_bytes)
            if (upload_token.status_code == 200) and (upload_token.content):
                create_body = json.dumps({"albumId":album_id, "newMediaItems":[{"description":"","simpleMediaItem":{"uploadToken":upload_token.content.decode()}}]}, indent=4)
                resp = session.post('https://photoslibrary.googleapis.com/v1/mediaItems:batchCreate', create_body).json()
                logging.debug("Server response: {}".format(resp))
                if "newMediaItemResults" in resp:
                    status = resp["newMediaItemResults"][0]["status"]
                    if status.get("code") and (status.get("code") > 0):
                        logging.error("Could not add \'{0}\' to library -- {1}".format(os.path.basename(photo_file_name), status["message"]))
                    else:
                        open(photo_file_name+".u", 'a').close()
                        logging.info("Added \'{}\' to library and album \'{}\' ".format(os.path.basename(photo_file_name), album_name))
                else:
                    logging.error("Could not add \'{0}\' to library. Server Response -- {1}".format(os.path.basename(photo_file_name), resp))
            else:
                logging.error("Could not upload \'{0}\'. Server Response - {1}".format(os.path.basename(photo_file_name), upload_token))
    try:
        del(session.headers["Content-type"])
        del(session.headers["X-Goog-Upload-Protocol"])
        del(session.headers["X-Goog-Upload-File-Name"])
    except KeyError:
       pass


logging.basicConfig(level=logging.INFO)
try:
    credentials = pickle.load(open('credentials','r'))
except:
    flow = InstalledAppFlow.from_client_secrets_file(
        'client_secret.json',
        scopes=['https://www.googleapis.com/auth/photoslibrary.readonly','https://www.googleapis.com/auth/photoslibrary.appendonly'])
    credentials = flow.run_console()
    with open("credentials","w") as outfile:
        pickle.dump(credentials,outfile)
session = AuthorizedSession(credentials);
album_id = create_or_retrieve_album(session, sys.argv[1]);
logging.info('Album id: '+album_id);
files = glob.glob(sys.argv[1]+'/*.???');
files_upld = glob.glob(sys.argv[1]+'/*.???.?');
logging.info('Photos in directory: '+str(files));
logging.info('Already uploaded: '+str(files_upld));
upload_photos(session, files, files_upld, album_id, sys.argv[1]);

