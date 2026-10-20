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
