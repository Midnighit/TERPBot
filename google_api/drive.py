from google_api import credentials
from googleapiclient.discovery import build
from apiclient.http import MediaIoBaseDownload, MediaFileUpload, MediaIoBaseUpload, HttpRequest, build_http
from zipfile import ZipFile
from shutil import rmtree
import io, os, codecs
import httplib2

service = build('drive', 'v3', credentials = credentials)

def list(queries = None):
    ''' List '''
    if queries == None:
        return service.files() \
            .list(fields = "files(id, name)") \
            .execute() \
            .get('files', [])
    else:
        return service.files() \
            .list(q = queries, fields = "files(id, name)") \
            .execute() \
            .get('files', [])

def getFileId(filename, queries = None):
    ''' Determine the id(s) matching the filename '''
    if queries == None:
        queries = "name = '" + filename + "'"
    else:
        queries = queries + " and name = '" + filename + "'"
    files = list(queries)
    out = []
    for file in files:
        if file['name'] == filename:
            out.append(file['id'])
    return out

def mkdir(path):
    ''' Create an empty folder within the given folder '''
    fType = 'application/vnd.google-apps.folder'
    query = "mimeType = 'application/vnd.google-apps.folder'"
    folders = path.split('/')
    curFolder = None
    while len(folders) > 0:
        checkFolder = folders.pop(0)
        fmd = {'name': checkFolder, 'mimeType': fType}
        # search folder in root directory
        if curFolder == None:
            curFolder = getFileId(checkFolder, query)
        # search folder as child of former curFolder
        else:
            fmd['parents'] = [curFolder]
            curFolder = getFileId(checkFolder, query +
                " and '" + curFolder + "' in parents")
        # pick first folder if it was found
        if len(curFolder) > 0:
            curFolder = curFolder[0]
        # create folder if it wasn't found
        else:
            curFolder = service.files() \
                .create(body = fmd, fields = 'id') \
                .execute() \
                .get('id')
    return curFolder

def upload(file, sourceMimeType, destinationMimeType, name = 'Template', path = None):
    ''' Upload(file, sourceMimeType, destinationMimeType) '''
    fileMetadata = {'name': name, 'mimeType': destinationMimeType}
    if path != None:
        fileMetadata['parents'] = [mkdir(path)]
    # if file is the name of the file(path)
    if file is str:
        media = MediaFileUpload(file, mimetype = sourceMimeType)
    # if file is the binary contents of the file itself
    else:
        media = MediaIoBaseUpload(file, mimetype = sourceMimeType)
    return service.files() \
        .create(body = fileMetadata, media_body = media, fields = 'id') \
        .execute() \
        .get('id')

def download(fileId, mimeType, fileName = 'export'):
    ''' Download(fileId, mimeType, fileName)'''
    request = service \
        .files() \
        .export_media(fileId = fileId, mimeType = mimeType)
    if fileName == False:
        fh = io.BytesIO()
    else:
        fh = io.FileIO(fileName, 'w')
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
    if fileName == False:
        fh.seek(0)
        return fh
    return True

def delete(fileId):
    ''' Delete(fileId) '''
    return service.files().delete(fileId = fileId).execute()

def getProperties(fileId):
    ''' Gets the metadata like title of the given file '''
    return service.files().get(fileId = fileId).execute()

def getName(fileId):
    ''' Gets the name of the file '''
    return getProperties(fileId)["name"]

def rename(fileId, title):
    ''' Renames the file '''
    return service.files() \
        .update(fileId = fileId, body = {"name": title}) \
        .execute()

def copy(fileId, title = "", path = None):
    ''' Copies a file '''
    if path != None:
        folderId = mkdir(path)
    return service.files().copy(
        fileId = fileId,
        body = {"name": title, "parents": [folderId]}) \
        .execute()

def move(fileId, path):
    ''' Moves a file to a new folder '''
    destFolderId = mkdir(path)
    sourceFolderId = service.files().get(
        fileId = fileId,
        fields='parents') \
        .execute()['parents'][0]
    return service.files().update(
        fileId = fileId,
        addParents = destFolderId,
        removeParents = sourceFolderId,
        fields = 'id, parents')\
        .execute()

def get_html_repr(spreadsheetId, sheetName, tmpDir = 'temp', cssDir = '/static/css/'):
    if not os.path.exists(tmpDir):
        os.makedirs(tmpDir)
    path = tmpDir + "/" + spreadsheetId + "/"
    download(spreadsheetId, "application/zip", tmpDir + "/export.zip")
    with ZipFile(tmpDir + "/export.zip") as zipRef:
        zipRef.extractall(path)
    if not os.path.isfile(path + sheetName + ".html"):
        return False
    with codecs.open(path + sheetName + ".html", encoding = 'utf8') as file:
        content = file.read()
    # clean up after having read the file
    os.remove(tmpDir + "/export.zip")
    rmtree(path)
    content = content.replace('href="resources/sheet.css"','href="' + cssDir + 'sheet.css"')
    return content

def handleResponse(resp,content):
    return content;

def getUrlViaHttp(url):
    token=credentials.token;
    headers={'Authorization': 'Bearer %s' % token}
    http=build_http()
    return HttpRequest(http=http,postproc=handleResponse,uri=url,headers=headers)
