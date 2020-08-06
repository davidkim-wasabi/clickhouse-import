import clickhouse_secrets as chcreds
from clickhouse_driver import Client
import sys

if len(sys.argv) > 1:
  file_name = sys.argv[1]
else:
  file_name = 'bucketUtils'
  print("No file name provided, defaulting to \"bucketUtils\"...")

if len(sys.argv) > 2:
  table_called = sys.argv[2]
else:
  table_called = 'bucket_utilization'
  print("No table name provided, defaulting to \"bucket_utilization\"...")

client = Client('localhost', user=chcreds.user, password=chcreds.password)
content = open('dbstarter/{}DbCreation.txt'.format(file_name), 'r').read().format(table_called)
query = content.replace('\n', ' ')

confirm_drop = input("Table \"{}\" might already exist on the database. \
Are you sure you want to replace it? [y/n] ".format(table_called))
if (confirm_drop == "y"):
  client.execute('DROP TABLE IF EXISTS billing_reports.{}'.format(table_called))
  client.execute(query)
  print("Created the table \"{}\".".format(table_called))
