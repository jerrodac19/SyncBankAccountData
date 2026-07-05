import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import json

def appendToSheet(new_data, sheetId='1DdYmC8wlCl8RK94n6h94lndXjmov412Y_tLC4_OGua0', sheetname = 'Transactions'):
    service = getSheetService()
    try:
        result = service.spreadsheets().values().append(
            spreadsheetId=sheetId,
            range=f'{sheetname}!A:Z',
            valueInputOption='USER_ENTERED',
            body={'values': new_data}
        ).execute()

        # 3. Log the Result
        appended_cells = result.get('updates', {}).get('updatedCells')
        print(f'{appended_cells} cells appended successfully.')

    except Exception as e:
        print(f'An error occurred: {e}')
    
def getSheetService():
    #Get Script Path
    workingDir = os.path.dirname(os.path.realpath(__file__))

    #Get Credentials for google tasks
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is created automatically when the authorization flow completes for the first time.
    if os.path.exists(workingDir + '\\token.pickle'):
        with open(workingDir + '\\token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        #else:
        #    flow = InstalledAppFlow.from_client_secrets_file(workingDir + '\\credentials.json', SCOPES)
        #    creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(workingDir + '\\token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    #Get sheets service
    return build('sheets', 'v4', credentials=creds)

"""
new_data = [
    ['12/08/2025', -35.03, 'PURCHASE AUTHORIZED ON 12/06 WM SUPERCENTER #2767 MESA AZ P000000382355118 CARD 6065'],
    ['12/08/2025', -12.34, 'PURCHASE AUTHORIZED ON 12/05 ARBYS 7116 MESA AZ S305339639708343 CARD 6065'],
    ['12/04/2025', -24.88, 'PURCHASE AUTHORIZED ON 12/04 WAL-MART #2767 MESA AZ P000000852428360 CARD 6065'],
    ['12/03/2025', -105.22, 'CITY OF MESA CHECKPYMT 251202 1072776177755 JERROD CORNEJO '],
    ['12/02/2025', -1808.69, 'ROCKET MORTGAGE MTG PYMTS 120125 3486715595 JERROD CORNEJO '],
    ['12/02/2025', -128.29, 'SRP ECHXPWR-ND 251201 XXXXX8001 Jerrod Cornejo '],
    ['12/01/2025', -412.51, 'COX COMM PHX PURCHASE 120125 5DnRK5z1a9mZSuh Jerrod Cornejo '],
    ['12/01/2025', -40.0, 'ZELLE TO AARON ON 11/30 REF # WFCT0ZJWSK8Y SODA'],
    ['12/01/2025', -14.07, 'RECURRING PAYMENT AUTHORIZED ON 11/29 PARAMOUNT+ 888-274-5343 CA S585334049504963 CARD 6065']
]

# 2. Execute the Append Request
try:
    result = service.spreadsheets().values().append(
        spreadsheetId='1DdYmC8wlCl8RK94n6h94lndXjmov412Y_tLC4_OGua0',
        range='Transactions!A:Z',
        valueInputOption='USER_ENTERED',
        body={'values': new_data}
    ).execute()

    # 3. Log the Result
    appended_cells = result.get('updates', {}).get('updatedCells')
    print(f'{appended_cells} cells appended successfully.')

except Exception as e:
    print(f'An error occurred: {e}')
"""
#response = service.spreadsheets().get(spreadsheetId='1DdYmC8wlCl8RK94n6h94lndXjmov412Y_tLC4_OGua0', fields='sheets.properties.title').execute()
#print(response)