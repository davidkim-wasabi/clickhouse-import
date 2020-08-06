print('starting script')
import clickhouse_secrets as chcreds
from googleapiclient.discovery import build, build_from_document
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from clickhouse_driver import Client
import pandas as pd, json, os, sys, base64
import datetime as dt
import time
print('imports complete')

path_prefix = os.path.dirname(os.path.abspath(__file__))
print('looking at path: {}'.format(path_prefix))
#looks through gmail history for automated e-mail with billing report attachments
def scrape_file_from_email(day, dest_folder):
    #get and refresh credentials from token
    try:    
        token_name = os.path.join(path_prefix,'gtoken.json')
        creds = Credentials.from_authorized_user_file(token_name)
        http_request = Request()
        creds.refresh(http_request)

        #build service and query gmail
        discovery_doc = json.load(open(os.path.join(path_prefix,'gmail-api.json'),'r'))
        service = build_from_document(discovery_doc, credentials = creds)
        #service = build('gmail', 'v1', credentials=creds)
        query = 'subject: "Daily billing reports from prod1" after:{}'.format(str(day))
        result = service.users().messages().list(userId='me', q = query).execute()

        #loop through message list, get message attachment and save each one
        for i in range(len(result['messages'])):
            #get message record
            msg_id = result['messages'][i]['id']
            msg = service.users().messages().get(userId='me', id=msg_id).execute()
            parts = msg['payload']['parts']

            #loop through attachments to find the user_current_stats
            #order changes on mondays, so we can't rely on a consistent index
            user_stat = None
            for part_idx in range(len(parts)-1,0,-1):
                part = parts[part_idx]
                if part['filename'] != 'user_current_stats_{}.csv'.format(str(day)): continue
                user_stat = part
                break

            if not user_stat: continue

            #get attachment details
            fname = user_stat['filename']
            atch_id = user_stat['body']['attachmentId']
            raw_data = service.users().messages().attachments().get(userId = 'me', messageId = msg_id, id = atch_id).execute()
            file_data = base64.urlsafe_b64decode(raw_data['data'].encode('UTF-8'))

            #write to billing reports folder
            path = os.path.join(path_prefix, dest_folder, fname)
            f = open(path, 'wb')
            f.write(file_data)
            f.close()
            return True
    except Exception as e:
        print('no email found')
        print(e)
    return False

#saves today's current_user_stats report to clickhouse
def add_data_to_DB(day, src_folder, dest_folder):
    try:
        columnTypes = json.load(open(os.path.join(path_prefix, 'columnTypes.json'),'r'))
        fname = 'user_current_stats_{}.csv'.format(day)
        path = os.path.join(path_prefix, src_folder,fname)
        data = pd.read_csv(path, dtype = columnTypes)
        data = data.fillna('Null')

        data['AccountCreatedAt'] = pd.to_datetime(data['AccountCreatedAt'])
        data['StorageStatsCurrentAsOf'] = pd.to_datetime(data['StorageStatsCurrentAsOf'])

        client = Client('localhost', user=chcreds.user, password=chcreds.password)
        table_name = 'userStats'

        client.execute('INSERT INTO {t} ({v}) VALUES'.format(t = table_name, v=','.join(data.columns)), data.to_dict('records'))
        os.rename(path, os.path.join(path_prefix, dest_folder,fname))
    except Exception as e:
        print(e)

print('initializing variables')
#determine date using an offset from the command line - default is today
day_offset = 0
if len(sys.argv) > 1:
    day_offset = int(sys.argv[1])
day = dt.date.today() - dt.timedelta(days = day_offset)

#initialize variables
initial_folder = 'billing reports'  #location to save from e-mail
final_folder = 'archive'            #location to save after db upload
start_time = time.time()
elapsed_time = time.time() - start_time
timeout = (3600 * 10) #timeout after 10 hours

print('start waiting for email')
#check every 5 minutes for the e-mail
while(not scrape_file_from_email(day, initial_folder) and elapsed_time < timeout):
    time.sleep(300)
    elapsed_time = time.time() - start_time
    print('elapsed time: {}'.format(elapsed_time))

#if we finish before timeout, then we have a file, so add it
if elapsed_time < timeout:
    print('email found')
    add_data_to_DB(day, initial_folder, final_folder)
    print('data added to database')
else:
    print('email not found - timeout')
