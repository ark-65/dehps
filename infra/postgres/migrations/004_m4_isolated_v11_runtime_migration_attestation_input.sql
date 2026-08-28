BEGIN;

LOCK TABLE m4_isolated_v11.registered_inputs IN ACCESS EXCLUSIVE MODE;

DO $migration$
DECLARE
  constraint_count INTEGER;
  current_definition TEXT;
  old_definition CONSTANT TEXT := $old$CHECK ((artifact_type = ANY (ARRAY['m4_isolated_24h_challenger_source_contract_v11'::text, 'M4IsolatedDatabaseSchemaIdentityV11'::text, 'M4IsolatedHistorySchemaInputV11'::text, 'M4IsolatedHistoryContentInputV11'::text, 'M4IsolatedAuditedDrawInputV11'::text])))$old$;
  new_definition CONSTANT TEXT := $new$CHECK ((artifact_type = ANY (ARRAY['m4_isolated_24h_challenger_source_contract_v11'::text, 'M4IsolatedDatabaseSchemaIdentityV11'::text, 'M4IsolatedHistorySchemaInputV11'::text, 'M4IsolatedHistoryContentInputV11'::text, 'M4IsolatedAuditedDrawInputV11'::text, 'M4IsolatedRuntimeMigrationAttestationInputV11'::text])))$new$;
BEGIN
  SELECT count(*), min(pg_get_constraintdef(oid))
  INTO constraint_count, current_definition
  FROM pg_constraint
  WHERE conrelid = 'm4_isolated_v11.registered_inputs'::regclass
    AND conname = 'registered_inputs_artifact_type_check'
    AND contype = 'c';

  IF constraint_count <> 1 THEN
    RAISE EXCEPTION
      'm4_isolated_v11 registered-input artifact-type constraint cardinality changed: %',
      constraint_count;
  END IF;

  IF current_definition = old_definition THEN
    ALTER TABLE m4_isolated_v11.registered_inputs
      DROP CONSTRAINT registered_inputs_artifact_type_check;
    ALTER TABLE m4_isolated_v11.registered_inputs
      ADD CONSTRAINT registered_inputs_artifact_type_check CHECK (artifact_type IN (
        'm4_isolated_24h_challenger_source_contract_v11',
        'M4IsolatedDatabaseSchemaIdentityV11',
        'M4IsolatedHistorySchemaInputV11',
        'M4IsolatedHistoryContentInputV11',
        'M4IsolatedAuditedDrawInputV11',
        'M4IsolatedRuntimeMigrationAttestationInputV11'
      ));
  ELSIF current_definition <> new_definition THEN
    RAISE EXCEPTION
      'm4_isolated_v11 registered-input artifact-type constraint definition changed: %',
      current_definition;
  END IF;

  SELECT count(*), min(pg_get_constraintdef(oid))
  INTO constraint_count, current_definition
  FROM pg_constraint
  WHERE conrelid = 'm4_isolated_v11.registered_inputs'::regclass
    AND conname = 'registered_inputs_artifact_type_check'
    AND contype = 'c';

  IF constraint_count <> 1 OR current_definition <> new_definition THEN
    RAISE EXCEPTION
      'm4_isolated_v11 registered-input artifact-type constraint verification failed';
  END IF;
END
$migration$;

COMMIT;
