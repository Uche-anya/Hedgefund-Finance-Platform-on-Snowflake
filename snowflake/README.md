# Snowflake SQL

The current deployment files are grouped by environment. Run them in order;
do not rerun the one-off investigation scripts for a new deployment.

| Folder | Purpose |
| --- | --- |
| [`prod`](prod) | PROD RAW objects, scoped access and the suspended close graph |
| [`test`](test) | TEST delivery stage, pipes and loader access |
| [`history`](history) | Earlier DEV setup, fixes and incident queries kept as evidence |

PROD order: `01_raw.sql`, `02_access.sql`, deploy and build dbt,
`03_model_read_access.sql`, then `04_task_access.sql` and `05_tasks.sql`.
The first three phases were applied for the manual October 16 close. Task
access and tasks are prepared but have not been applied. The scheduled root
must stay suspended until the next-day producer and deadline checks pass.
`04_task_access.sql` temporarily gives the installing user the task role;
`05_tasks.sql` removes that personal grant after installing the graph. If
installation fails before the last statement, run the three cleanup statements
at the end of `05_tasks.sql` separately. The dedicated task role keeps task
ownership and its narrow PROD grants.
The graph in `05_tasks.sql` still contains the October rehearsal's scenario and
opening date. Do not install or schedule it as a general daily PROD graph until
those inputs are derived from the daily close contract and exercised in TEST.
