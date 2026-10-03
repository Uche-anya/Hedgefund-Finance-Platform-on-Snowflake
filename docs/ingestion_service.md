# Ingestion service identity

Daily file loading uses `NORTHBRIDGE_INGEST_LOCAL`, a Snowflake service user with
its own encrypted RSA key. The key file is under `.secrets`; its passphrase is in
Windows Credential Manager. Neither is committed to Git.

The `NORTHBRIDGE_INGEST` role can use the small warehouse, read and write the two
current internal stages, and select/insert into `RAW.REPLAY_INPUTS` and
`RAW.BROKER_POSITIONS`. It cannot create, replace, update or delete warehouse
objects. Adding another daily source requires an explicit table and stage grant.

Run the current loader with:

```powershell
python scripts/load_daily_inputs.py
```

The loader verifies both source hashes, uploads the files and uses `COPY` with
`FORCE = FALSE`. It then verifies 6,394 replay rows and 40 broker rows. An exact
retry is safe because Snowflake copy history skips a file it has already loaded.

`scripts/ingest_key.py` creates or verifies the local key and writes the ignored,
machine-specific bootstrap file `snowflake/27_ingest_key_access.sql`. Running that
SQL requires an administrator once. Normal ingestion does not use the personal
administrator connection, password or MFA.
