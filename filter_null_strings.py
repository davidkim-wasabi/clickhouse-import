import clickhouse_secrets as chcreds
from clickhouse_driver import Client
from clickhouse_driver import errors
import argparse
from json_serializer import to_json


# Returns the list of tables from the database.
def count_null_values(client, db, file=None):
  query_params = {"db": db}
  tables = client.execute("SHOW TABLES FROM {db}".format(**query_params))

  # Gather the columns from the schemas of each table and store them in a dictionary
  table_schemas = {}
  for table, in tables:
    query_params["tbl"] = table
    _, schema = client.execute("SELECT * FROM {db}.{tbl} WHERE 0".format(**query_params),
                               with_column_types=True)
    table_schemas[table] = cols = schema

    # Now, get the count of null values within EACH column of EVERY table. Phew!
    i = 0
    while i < len(cols):  # while > for, because we change the index in the loop
      query_params["col"], col_type = cols[i]

      # Check if the column is of type String
      if "string" in col_type.lower():
        null_count, = client.execute(
            "SELECT count() FROM {db}.{tbl} WHERE isNull({col}) OR lower({col}) = 'null' OR {col} = ''"
            .format(**query_params))[0]
      # Not a string, so we need to only check if it is null
      else:
        null_count, = client.execute(
            "SELECT count() FROM {db}.{tbl} WHERE isNull({col})".format(**query_params))[0]

      # We don't care about nonzero null values, just want the positives
      if null_count == 0:
        del table_schemas[table][i]
        i = i - 1  # remember to decrement the index because we deleted from a list!
      # Write our result for that column, overwriting the previous entry (col_type) with the count
      else:
        # While we're at it, change the column type of the suspect to Nullable
        if "Nullable" not in col_type:
          try:  # We need to catch exceptions and keep going to stay consistent
            query_params["col_type"] = col_type
            client.execute("ALTER TABLE {db}.{tbl} MODIFY COLUMN {col} Nullable({col_type})".format(
                **query_params))
          except errors.ServerException as e:  # Raised when the op fails, e.g. targeting index col
            print(e)
        table_schemas[table][i] = (table_schemas[table][i][0], null_count)

      i = i + 1

  # Pretty-print into JSON
  json_out = to_json(table_schemas)

  # Depending on optional argument, write to file or just dump
  if file is not None:
    outfile = open(file, "w")
    outfile.write(json_out)
    outfile.close()
  else:
    print(json_out)


# Runs when the code is run as a script.
if __name__ == "__main__":
  parser = argparse.ArgumentParser(
      description=
      "Counts the number of null values for each column of every table in a ClickHouse database.")
  parser.add_argument("-f", "--file", type=str, help="the file to which the output is written")
  parser.add_argument("-d",
                      "--db",
                      type=str,
                      default="billing_reports",
                      help="the database to connect to")
  args = parser.parse_args()

  client = Client("localhost", user=chcreds.user, password=chcreds.password)
  count_null_values(client, args.db, args.file)
