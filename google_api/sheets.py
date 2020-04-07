from google_api import credentials
from googleapiclient.discovery import build

service = build('sheets', 'v4', credentials = credentials)
updates = {}

def commit():
    ''' Execute all the requests collected in updates '''
    global updates
    for id, requests in updates.items():
        return service.spreadsheets().batchUpdate(
            spreadsheetId = id,
            body = requests) \
            .execute()
    updates = {}

def convertR1toA1(col):
    R1 = ""
    while col > 0:
        col, remainder = divmod(col - 1, 26)
        R1 = chr(65 + remainder) + R1
    return R1

def getMetadata(spreadsheetId):
    ''' Get sheets metadata '''
    return service.spreadsheets() \
        .get(spreadsheetId = spreadsheetId) \
        .execute()['sheets']

def getProperties(spreadsheetId, sheetId):
    ''' Get sheet properties '''
    sheets = getMetadata(spreadsheetId)
    if type(sheetId) is str and sheetId.isnumeric():
        sheetId = int(sheetId)
    if type(sheetId) is int:
        for sheet in sheets:
            if sheet['properties']['sheetId'] == sheetId:
                return sheet['properties']
    elif type(sheetId) is str:
        for sheet in sheets:
            if sheet['properties']['title'] == sheetId:
                return sheet['properties']
    return False

def getSheetId(spreadsheetId, sheetName):
    sheets = getMetadata(spreadsheetId)
    for sheet in sheets:
        if sheet['properties']['title'] == sheetName:
            return sheet['properties']['sheetId']
    return False

def getSheetName(spreadsheetId, sheetId):
    sheets = getMetadata(spreadsheetId)
    for sheet in sheets:
        if sheet['properties']['sheetId'] == sheetId:
            return sheet['properties']['title']
    return False

def duplicateSheet(sourceSpreadsheetId, sourceSheetId, destinationSpreadsheetId, newSheetName = None):
    ''' Copy a sheet into an existing Spreadsheet '''
    if type(sourceSheetId) is str and sourceSheetId.isnumeric():
        sourceSheetId = int(sourceSheetId)
    elif type(sourceSheetId) is str:
        sourceSheetId = getSheetId(sourceSpreadsheetId, sourceSheetId)
    body = {"destinationSpreadsheetId": destinationSpreadsheetId}
    response = service.spreadsheets().sheets().copyTo(
            spreadsheetId = sourceSpreadsheetId,
            sheetId = sourceSheetId,
            body = body) \
            .execute()
    if newSheetName == None:
        newSheetName = getProperties(sourceSpreadsheetId, sourceSheetId)['title']
    rename(destinationSpreadsheetId, response['sheetId'], newSheetName)
    response['title'] = newSheetName
    return response

def read(spreadsheetId, range, value_render_option = 'UNFORMATTED_VALUE'):
    ''' Read the cells within the given range'''
    return service.spreadsheets().values().get(
        spreadsheetId = spreadsheetId,
        range = range,
        valueRenderOption = value_render_option) \
        .execute() \
        .get('values', [])

def update(spreadsheetId, range, values, valueInputOption = 'USER_ENTERED'):
    ''' Update the cells within the given range '''
    valueRangeBody = {"values": values}
    return service.spreadsheets().values().update(
        spreadsheetId = spreadsheetId,
        range = range,
        valueInputOption = valueInputOption,
        body = valueRangeBody) \
        .execute()

def createSpreadsheet(spreadsheetTitle, sheetTitles):
    ''' Creates an empty spreadsheet with some sheets '''
    spreadsheetBody = {
        "properties": {"title": spreadsheetTitle},
        "sheets": []
    }
    if type(sheetTitles) is str:
        sheetTitles = [sheetTitles]
    for title in sheetTitles:
        spreadsheetBody["sheets"].append({"properties": {"title": title} })
    return service.spreadsheets().create(body = spreadsheetBody).execute()

def rename(spreadsheetId, arg1, arg2 = None):
    ''' Renames a sheet or spreadsheet '''
    if not spreadsheetId in updates:
        updates[spreadsheetId] = {'requests': []}
    # if only one argument is passed => rename whole spreadsheet
    if arg2 == None:
        updates[spreadsheetId]['requests'].append({
            "updateSpreadsheetProperties": {
                "fields": "title",
                "properties": {"title": arg1}
            }
        })
    # if two arguments are passed => rename just the sheet
    else:
        updates[spreadsheetId]['requests'].append({
            "updateSheetProperties": {
                "fields": "title",
                "properties": {"sheetId": arg1, "title": arg2}
            }
        })

def setGridSize(spreadsheetId, sheetId, cols, rows, frozen = 0):
    ''' Sets the gridsize of the sheet '''
    if type(sheetId) is str and sheetId.isnumeric():
        sheetId = int(sheetId)
    elif type(sheetId) is str:
        sheetId = getSheetId(spreadsheetId, sheetId)
    if not spreadsheetId in updates:
        updates[spreadsheetId] = {'requests': []}
    updates[spreadsheetId]['requests'].append({
        "updateSheetProperties": {
            "fields": "gridProperties",
            "properties": {
                "sheetId": sheetId,
                "gridProperties": {
                    "columnCount": cols,
                    "rowCount": rows,
                    "frozenRowCount": frozen
                }
            }
        }
    })

def setDimensionGroup(spreadsheetId, sheetId, startIndex, endIndex, dimension = 'ROWS'):
    if type(sheetId) is str and sheetId.isnumeric():
        sheetId = int(sheetId)
    elif type(sheetId) is str:
        sheetId = getSheetId(spreadsheetId, sheetId)
    if not spreadsheetId in updates:
        updates[spreadsheetId] = {'requests': []}
    updates[spreadsheetId]['requests'].append({
        "addDimensionGroup": {
            "range": {
                "sheetId": sheetId,
                "startIndex": startIndex,
                "endIndex": endIndex,
                "dimension": dimension
            }
        }
    })

def deleteDimensionGroup(spreadsheetId, sheetId, startIndex, endIndex, dimension = 'ROWS'):
    if type(sheetId) is str and sheetId.isnumeric():
        sheetId = int(sheetId)
    elif type(sheetId) is str:
        sheetId = getSheetId(spreadsheetId, sheetId)
    if not spreadsheetId in updates:
        updates[spreadsheetId] = {'requests': []}
    updates[spreadsheetId]['requests'].append({
        "deleteDimensionGroup": {
            "range": {
                "sheetId": sheetId,
                "startIndex": startIndex,
                "endIndex": endIndex,
                "dimension": dimension
            }
        }
    })

def addNamedRange(spreadsheetId, sheetId, name, namedRangeId = None, startCol = None, startRow = None, endCol = None, endRow = None):
    if type(sheetId) is str and sheetId.isnumeric():
        sheetId = int(sheetId)
    elif type(sheetId) is str:
        sheetId = getSheetId(spreadsheetId, sheetId)
    if not spreadsheetId in updates:
        updates[spreadsheetId] = {'requests': []}
    updates[spreadsheetId]['requests'].append({
        "addNamedRange": {
            "namedRange": {
                "name": name,
                "range": {
                    "sheetId": sheetId
                }
            }
        }
    })
    idx = len(updates[spreadsheetId]['requests']) - 1
    if namedRangeId:
        updates[spreadsheetId]['requests'][idx]["addNamedRange"]["namedRange"]["namedRangeId"] = str(namedRangeId)
    if startCol:
        updates[spreadsheetId]['requests'][idx]["addNamedRange"]["namedRange"]["range"]['startColumnIndex'] = startCol - 1
    if endCol:
        updates[spreadsheetId]['requests'][idx]["addNamedRange"]["namedRange"]["range"]['endColumnIndex'] = endCol
    if startRow:
        updates[spreadsheetId]['requests'][idx]["addNamedRange"]["namedRange"]["range"]['startRowIndex'] = startRow - 1
    if endRow:
        updates[spreadsheetId]['requests'][idx]["addNamedRange"]["namedRange"]["range"]['endRowIndex'] = endRow

def crop(spreadsheetId, sheetId, frozen = 0):
    sheetName = ''
    if type(sheetId) is str and sheetId.isnumeric():
        sheetId = int(sheetId)
        sheetName = getSheetName(spreadsheetId, sheetId)
    elif type(sheetId) is str:
        sheetName = sheetId
        sheetId = getSheetId(spreadsheetId, sheetName)
    if sheetName == '':
        sheetName = getSheetName(spreadsheetId, sheetId)
    results = getProperties(spreadsheetId, sheetId)
    rows = results['gridProperties']['rowCount']
    cols = results['gridProperties']['columnCount']
    range = sheetName + '!A1:' + convertR1toA1(cols) + str(rows)
    results = read(spreadsheetId, range)
    maxRows = 1
    maxColumns = 1
    idx = 0
    for currRow in results:
        columnsInCurrRow = len(currRow)
        if columnsInCurrRow > 0:
            maxRows = idx + 1
            maxColumns = max(maxColumns, columnsInCurrRow)
        idx = idx + 1
    setGridSize(spreadsheetId, sheetId, maxColumns, maxRows, frozen)
    return [maxColumns, maxRows]

def export(spreadsheetId, format, **kwargs):
    ''' Exports the Spreadsheet using a variable number of arguments

    MANDATORY ARGUMENTS:
    spreadsheetId                   # spreadsheet or fileId
    format = 'pdf'                  # pdf/xlsx/ods/csv/tsv/zip(=html)

    DEFAULT ARGUMENTS
    scale = '1',                    # 1 = Normal 100%/2 = Fit to width/3 = Fit to height/4 = Fit to Page
    gridlines = 'false',            # true/false
    printnotes = 'false',           # true/false
    printtitle = 'false',           # true/false
    sheetnames = 'false',           # true/false
    attachment = 'true',            # true/false Opens a download dialog/displays the file in the browser

    OPTIONAL ARGUMENTS:
    sheetId = 123456789             # whole spreadsheet will be printed if not given
    portrait = 'false'              # true = Portrait/false = Landscape
    fitw = 'true'                   # true/false fit to window or actual size
    size = 'a4',                    # A3/A4/A5/B4/B5/letter/tabloid/legal/statement/executive/folio
    top_margin = '1.5'              # All four margins must be set!
    bottom_margin = '1.5'           # All four margins must be set!
    left_margin = '2.0'             # All four margins must be set!
    right_margin = '3.0'            # All four margins must be set!
    pageorder = '1'                 # 1 = Down, then over / 2 = Over, then down
    horizontal_alignment = 'CENTER' # LEFT/CENTER/RIGHT
    vertical_alignment = 'MIDDLE'   # TOP/MIDDLE/BOTTOM
    fzr = 'true'                    # repeat row headers
    fzc = 'true'                    # repeat column headers

    RANGE ARGUMENTS:
    range = 'MyNamedRange'          # Name of the actual range
    ir = 'false'                    # true/false (seems to be always false)
    ic = 'false'                    # same as ir
    r1 = '0'                        # Start Row number-1 (row 1 would be 0)
    c1 = '0'                        # Start Column number-1 (Column 1 would be 0)
    r2 = '15'                       # End Row number
    c2 = '6'                        # End Column number
    '''

    # Set default arguments
    if 'scale' not in kwargs:
        kwargs['scale'] = '1'
    if 'gridlines' not in kwargs:
        kwargs['gridlines'] = 'false'
    if 'printnotes' not in kwargs:
        kwargs['printnotes'] = 'false'
    if 'printtitle' not in kwargs:
        kwargs['printtitle'] = 'false'
    if 'sheetnames' not in kwargs:
        kwargs['sheetnames'] = 'false'
    if 'attachment' not in kwargs:
        kwargs['attachment'] = 'true'

    # make sure the format given is one of those allowed
    possible_formats = ['pdf', 'xlsx', 'ods', 'csv', 'tsv', 'zip']
    if format not in possible_formats:
        return format + ' is not a valid export format!'
    # the google api calls the sheetId 'gid', so we fix this if not passed that way already
    if 'sheetId' in kwargs:
        kwargs['gid'] = kwargs['sheetId']
        del kwargs['sheetId']

    # Create url
    url = 'https://docs.google.com/spreadsheets/d/' + spreadsheetId + '/export?format=' + format
    for k, v in kwargs.items():
        url = url + '&' + k + '=' + str(v)
    return url

def check(spreadsheetId, sheetId = None):
    values = []
    if sheetId == None:
        sheets = getMetadata(spreadsheetId)
        for sheet in sheets:
            chk = check(spreadsheetId, sheet['properties']['sheetId'])
            if chk:
                values = values + chk
    else:
        sheetName = ''
        if type(sheetId) is str and sheetId.isnumeric():
            sheetId = int(sheetId)
            sheetName = getSheetName(spreadsheetId, sheetId)
        elif type(sheetId) is str:
            sheetName = sheetId
            sheetId = getSheetId(spreadsheetId, sheetName)
        if sheetName == '':
            sheetName = getSheetName(spreadsheetId, sheetId)
        results = getProperties(spreadsheetId, sheetId)
        rows = results['gridProperties']['rowCount']
        cols = results['gridProperties']['columnCount']
        range = sheetName + '!A1:' + convertR1toA1(cols) + str(rows)
        results = read(spreadsheetId, range)
        rowIdx = 0
        for currRow in results:
            rowIdx = rowIdx + 1
            colIdx = 0
            for currCell in currRow:
                colIdx = colIdx + 1
                if currCell == '#ERROR!' or \
                    currCell == '#NAME?' or \
                    currCell == '#REF!':
                    values.append(sheetName + '!' + convertR1toA1(colIdx) + str(rowIdx))
    if values == []:
        return None
    return values
