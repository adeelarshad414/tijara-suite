# PostgreSQL Operations

Production deployments should use managed PostgreSQL where possible. For
self-hosted customers, use PostgreSQL 16+, pgBackRest or Restic-backed logical
and physical backups, point-in-time recovery, and separate credentials for
application, migration, and read-only reporting access.

Minimum production controls:

- Daily encrypted backups.
- Restore drill before go-live.
- Separate backup storage account.
- WAL archiving for larger tenants.
- Database-per-tenant for SaaS isolation unless a customer explicitly requires
  a dedicated deployment.
- Database password is supplied from `secrets/.env.secrets` for local/staging
  and from a managed secret store in production.
- Backup encryption key is supplied from `BACKUP_ENCRYPTION_KEY`; never store it
  beside the backup artifact.

Logical backup shape for pilots:

```bash
docker compose --env-file .env --env-file secrets/.env.secrets exec db pg_dump -U "$POSTGRES_USER" -Fc tenant_database_name
```

Production should wrap this with timestamped output, encryption, offsite upload,
and restore verification.
