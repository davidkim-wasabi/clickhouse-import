# ClickHouse-import
Scripts related to importing data into ClickHouse, initializing new tables, filtering nulls, and so forth.

To set the credentials for ClickHouse, create a file `clickhouse_secrets.py` and set `user` and `password` variables appropriately.

Example usage: 
```python
os.system('tail -n +2 TaxJarTaxCalc.csv | \
docker exec -i clickhouse-server clickhouse-client --user {} --password {} \
--query="INSERT INTO BA_Billing.TaxJarTaxCalc FORMAT CSV"'.format(clickhouse_secrets.user, clickhouse_secrets.password))
```
