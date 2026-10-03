# NAV publication and restatement

`fct_daily_nav` is a current calculation table and may be rebuilt. Published
values are copied into append-only tables in `NORTHBRIDGE_DEV.OPERATIONS`.

The `NORTHBRIDGE_NAV_PUBLISHER` role can select candidates and insert operational
history. It has no update or delete grants. The three ledgers are:

- `PIPELINE_RUN_EVENTS`: started, succeeded and failed calculation events;
- `NAV_PUBLICATIONS`: the value published for each account and input version;
- `NAV_RESTATEMENTS`: the original and replacement publications, difference,
  reason and approver when a published value changes.

The run ID is derived from the business date, scenario, three delivery IDs and a
hash of the dbt project. Retrying the same inputs and code reuses the run instead
of inserting duplicate publication rows.

Run from the repository root:

```powershell
python scripts/publish_nav.py
```

The command connects as the dedicated service user
`NORTHBRIDGE_NAV_PUBLISHER_LOCAL` with an encrypted RSA key. Its private key is
under `.secrets`; the unlock secret is in Windows Credential Manager. The dbt
service user does not receive the publisher role.

The January configuration contains a clearly marked simulated control note for
the three known broker test breaks. Without that note, publication stops. If an
account NAV changes after publication, the command also stops unless both
`--restatement-reason` and `--approved-by` are supplied. A successful correction
appends new publication and restatement rows; it never edits the old NAV.
