import clickhouse_secrets as chcreds
from clickhouse_driver import Client
import datetime as dt
from progress.bar import IncrementalBar as Bar
from googleapiclient.discovery import build, build_from_document
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import pandas as pd, json, os, sys, base64, numpy as np
import time, traceback
path_prefix = os.path.dirname(os.path.abspath(__file__))

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
            for part_idx in range(1,len(parts)): #start at 1 since first part is main body
                try:
                    part = parts[part_idx]

                    #get attachment details
                    fname = part['filename']
                    atch_id = part['body']['attachmentId']
                    raw_data = service.users().messages().attachments().get(userId = 'me', messageId = msg_id, id = atch_id).execute()
                    file_data = base64.urlsafe_b64decode(raw_data['data'].encode('UTF-8'))

                    #write to billing reports folder
                    path = os.path.join(path_prefix, dest_folder, fname)
                    with open(path, 'wb') as f:
                        f.write(file_data)
                
                #fail to write file
                except Exception as e:
                    print('failed to write file')
                    print(e)
            
            return True
    except Exception as e:
        print('no email found')
        print(e)
    return False

def get_report_data(fpath = path_prefix, fname = 'BillingReportInventory.csv', ready_only = True):
    billing_report_data = pd.read_csv(os.path.join(fpath, fname), index_col = 'Report') #csv holds report info
    if ready_only:
        billing_report_data = billing_report_data[billing_report_data['Ready?'] == 'Yes']
    #compare_len = min([len(x) for x in billing_report_data['Report Name']])
    #billing_report_data['Report Name'] = [x[:compare_len] for x in billing_report_data['Report Name']]
    return billing_report_data

def process_folder(folder = 'billing reports', typedir = 'typejsons', legacy = False):
    chunk_size = 10 ** 6
    files = os.listdir(os.path.join(path_prefix,folder))
    report_data = get_report_data()
    bar = Bar('Processing', max = len(files))
    for fname in files:
        process_file(fname, report_data, folder, typedir = typedir, legacy = legacy)
        bar.next()

def process_file(fname, report_data, srcdir = 'billing reports', destdir = 'archive', typedir = 'typejsons', legacy = False):
        compare_name = fname[:-14]
        #print(compare_name)
        if not compare_name in report_data['Report Name'].to_list(): return
        #print(fname)
        try: 
            report = report_data[report_data['Report Name'] == compare_name].index.values[0]
            vals = report_data.loc[report]

            floc = os.path.join(path_prefix, srcdir, fname)

            if vals['Remove File'] == 'Yes':
                os.remove(floc) 
                return

            #load dict of types from json
            json_base = '{}-legacy.json' if legacy else '{}.json'
            json_name = json_base.format(report)
            json_floc = os.path.join(path_prefix, typedir, json_name)
            with open(json_floc, 'r') as fp:
                types = json.loads(json.load(fp))

            #load data with correct types
            chunk_size = 10 ** 6
            for chunk in pd.read_csv(floc, dtype = types, chunksize = chunk_size, thousands=','):
                data = chunk
                data.columns = list(types.keys())
                #update datetime columns
                if not vals['Date Column'] is np.nan:
                    for date_col in [x.strip() for x in vals['Date Column'].split(',')]:
                        data[date_col] = pd.to_datetime(data[date_col]).fillna(dt.datetime(1970,1,1,0,0,0))

                data.loc[:,data.select_dtypes(include = 'string').columns] = data.select_dtypes(include = 'string').fillna('Null')
                #data.loc[:,data.select_dtypes(include = 'number').columns] = data.select_dtypes(include = 'number').fillna(0)
                #handle files that don't have a date columns
                if vals['Add Index Date'] == 'Yes':
                    data['Date'] = pd.to_datetime(fname[-14:-4])

                #handle files that span multiple days
                if vals['TimeRange Overlap'] == 'Yes':
                    import_vals = [data.iloc[:2].to_dict('records')[0]]
                else:
                    import_vals = data.to_dict('records')

                #add reports to clickhouse
                client = Client('localhost', user=chcreds.user, password=chcreds.password)
                table_base = 'billing_reports.{}_legacy' if legacy else 'billing_reports.{}'
                table_name = table_base.format(vals['Table Name'])
                client.execute('INSERT INTO {t} ({v}) VALUES'.format(t = table_name, v=','.join(data.columns)), import_vals)
            #move report to archive when done
            
            os.rename(floc, os.path.join(path_prefix, destdir, fname))

        except Exception as e:
            print('failed to load file {}'.format(fname))
            traceback.print_exc()


