import clickhouse_secrets as chcreds
from clickhouse_driver import Client
import sys

client = Client("localhost", user=chcreds.user, password=chcreds.password)

base_path = os.path.join("home", "users", "dkim", "mysql_data_transfer", "GDB_dbstarter")
global_tables = os.listdir(os.path.join(base_path, "BA_Global"))
billing_tables = os.listdir(os.path.join(base_path, "BA_Billing"))

# Create the necessary databases if they don't exist already
client.execute("CREATE DATABASE IF NOT EXISTS BA_Global")
client.execute("CREATE DATABASE IF NOT EXISTS BA_Billing")

for tbl in global_tables:
  if ".txt" in tbl:
    content = open(tbl, "r").read()
    query = content.replace("\n", " ")

    table_name = os.path.splitext(tbl)[0]
    client.execute("DROP TABLE IF EXISTS BA_Global.{}".format(table_name))
    client.execute(query)
    print("Created the table BA_Global.\"{}\".".format(table_name))

for tbl in billing_tables:
  if ".txt" in tbl:
    content = open(tbl, "r").read()
    query = content.replace("\n", " ")

    table_name = os.path.splitext(tbl)[0]
    client.execute("DROP TABLE IF EXISTS BA_Billing.{}".format(table_name))
    client.execute(query)
    print("Created the table BA_Billing.\"{}\".".format(table_name))