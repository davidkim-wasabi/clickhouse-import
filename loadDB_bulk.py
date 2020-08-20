import clickhouse_secrets as chcreds
from clickhouse_driver import Client
import sys
import os

client = Client("localhost", user=chcreds.user, password=chcreds.password)

base_path = os.path.join("/home", "users", "dkim", "mysql_data_transfer")
global_tables = os.listdir(os.path.join(base_path, "BA_Global"))
billing_tables = os.listdir(os.path.join(base_path, "BA_Billing"))

for tbl in global_tables:
  if ".csv" in tbl:
    tbl_name = os.path.splitext(tbl)[0]
    os.system('cat {}.csv | \
        docker exec -i clickhouse-server clickhouse-client --user admin \
        --password 4irehose --query="INSERT INTO BA_Global.{} FORMAT CSV"'.format(
          os.path.join(base_path, "BA_Global", tbl_name), tbl_name))

for tbl in billing_tables:
  if ".csv" in tbl:
    tbl_name = os.path.splitext(tbl)[0]
    os.system('cat {}.csv | \
        docker exec -i clickhouse-server clickhouse-client --user admin \
        --password 4irehose --query="INSERT INTO BA_Billing.{} FORMAT CSV"'.format(
        os.path.join(base_path, "BA_Billing", tbl_name), tbl_name))