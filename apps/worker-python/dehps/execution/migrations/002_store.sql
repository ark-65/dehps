-- Same NOLOGIN owner as 001_authority; canonical Research OS schema must exist.
-- Additive: never migrate or rewrite historical execution records.
CREATE SCHEMA execution_store;
REVOKE ALL ON SCHEMA execution_store FROM PUBLIC;
CREATE TABLE execution_store.tasks (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    control_plane text NOT NULL REFERENCES public.research_os_control_planes(control_plane_key),
    business_key text NOT NULL CHECK (length(business_key) BETWEEN 1 AND 500),
    task_digest text NOT NULL REFERENCES public.research_os_task_definitions(task_digest),
    manifest_digest text NOT NULL,
    scientific_contract_sha256 text NOT NULL CHECK (scientific_contract_sha256 ~ '^[0-9a-f]{64}$'),
    release_sha256 text NOT NULL CHECK (release_sha256 ~ '^[0-9a-f]{64}$'),
    verifier_id text NOT NULL CHECK (length(verifier_id) BETWEEN 1 AND 200),
    artifact_schema text NOT NULL CHECK (length(artifact_schema) BETWEEN 1 AND 200),
    spec jsonb NOT NULL,
    UNIQUE (control_plane, business_key),
    FOREIGN KEY (manifest_digest,task_digest) REFERENCES public.research_os_manifest_tasks(manifest_digest,task_digest)
);
CREATE TABLE execution_store.attempts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id bigint NOT NULL REFERENCES execution_store.tasks(id),
    authority_execution bigint NOT NULL REFERENCES execution_authority.executions(id),
    fence bigint NOT NULL CHECK (fence > 0),
    status text NOT NULL CHECK (status IN ('running','failed','completed')),
    reason text,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    finished_at timestamptz,
    UNIQUE (task_id,fence),
    UNIQUE (task_id,id)
);
CREATE TABLE execution_store.leases (
    task_id bigint PRIMARY KEY REFERENCES execution_store.tasks(id),
    attempt_id uuid NOT NULL,
    fence bigint NOT NULL,
    expires_at timestamptz NOT NULL,
    FOREIGN KEY (task_id,attempt_id) REFERENCES execution_store.attempts(task_id,id)
);
CREATE TABLE execution_store.commits (
    task_id bigint PRIMARY KEY REFERENCES execution_store.tasks(id),
    attempt_id uuid NOT NULL UNIQUE,
    artifact_sha256 text NOT NULL CHECK (artifact_sha256 ~ '^[0-9a-f]{64}$'),
    artifact_size bigint NOT NULL CHECK (artifact_size >= 0),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY (task_id,attempt_id) REFERENCES execution_store.attempts(task_id,id)
);
CREATE TRIGGER execution_tasks_immutable BEFORE UPDATE OR DELETE ON execution_store.tasks
FOR EACH ROW EXECUTE FUNCTION public.dehps_research_os_reject_immutable_mutation();
CREATE TRIGGER execution_commits_immutable BEFORE UPDATE OR DELETE ON execution_store.commits
FOR EACH ROW EXECUTE FUNCTION public.dehps_research_os_reject_immutable_mutation();

CREATE FUNCTION execution_store.plan_actor(p_execution bigint, p_content text, p_release text, p_spec jsonb)
RETURNS execution_authority.identities LANGUAGE plpgsql
SET search_path=pg_catalog,pg_temp AS $$
DECLARE a execution_authority.identities; payload jsonb;
BEGIN
    PERFORM execution_authority.reauthorize(p_execution,p_content,p_release);
    a := execution_authority.actor('execute');
    SELECT r.payload INTO payload FROM execution_authority.requests r
        JOIN execution_authority.executions e ON e.request_id=r.id WHERE e.id=p_execution;
    IF payload->>'schema' IS DISTINCT FROM 'execution-plan.v1'
        OR payload - ARRAY['schema','tasks'] IS DISTINCT FROM '{}'::jsonb
        OR jsonb_typeof(payload->'tasks') IS DISTINCT FROM 'array' THEN
        RAISE EXCEPTION 'closed execution plan required' USING ERRCODE='42501';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM jsonb_array_elements(payload->'tasks') entry WHERE entry=p_spec) THEN
        RAISE EXCEPTION 'task outside approved execution plan' USING ERRCODE='42501';
    END IF;
    RETURN a;
END $$;

CREATE FUNCTION execution_store.register_task(p_execution bigint, p_content text, p_release text, p_spec jsonb)
RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,pg_temp AS $$
DECLARE a execution_authority.identities; t execution_store.tasks;
BEGIN
    a := execution_store.plan_actor(p_execution,p_content,p_release,p_spec);
    IF jsonb_typeof(p_spec) IS DISTINCT FROM 'object' OR
        p_spec - ARRAY['business_key','task_digest','manifest_digest','scientific_contract_sha256','verifier_id','artifact_schema'] <> '{}'::jsonb THEN
        RAISE EXCEPTION 'invalid task specification';
    END IF;
    INSERT INTO execution_store.tasks
        (control_plane,business_key,task_digest,manifest_digest,scientific_contract_sha256,release_sha256,verifier_id,artifact_schema,spec)
    VALUES (a.control_plane,p_spec->>'business_key',p_spec->>'task_digest',p_spec->>'manifest_digest',
        p_spec->>'scientific_contract_sha256',p_release,p_spec->>'verifier_id',p_spec->>'artifact_schema',p_spec)
    ON CONFLICT (control_plane,business_key) DO NOTHING;
    SELECT * INTO t FROM execution_store.tasks WHERE control_plane=a.control_plane AND business_key=p_spec->>'business_key';
    IF t.spec IS DISTINCT FROM p_spec OR t.release_sha256 IS DISTINCT FROM p_release THEN
        RAISE EXCEPTION 'business key already bound to another definition' USING ERRCODE='23505';
    END IF;
    RETURN t.id;
END $$;

CREATE FUNCTION execution_store.lock_task(p_task bigint, p_execution bigint, p_content text, p_release text)
RETURNS execution_store.tasks LANGUAGE plpgsql
SET search_path=pg_catalog,pg_temp AS $$
DECLARE a execution_authority.identities; t execution_store.tasks;
BEGIN
    -- Authorization first; all transitions acquire locks in the same order.
    PERFORM execution_authority.reauthorize(p_execution,p_content,p_release);
    SELECT * INTO t FROM execution_store.tasks WHERE id=p_task;
    IF NOT FOUND THEN RAISE EXCEPTION 'task unavailable' USING ERRCODE='42501'; END IF;
    a := execution_store.plan_actor(p_execution,p_content,p_release,t.spec);
    IF t.control_plane <> a.control_plane OR t.release_sha256 <> p_release THEN
        RAISE EXCEPTION 'task identity mismatch' USING ERRCODE='42501';
    END IF;
    PERFORM 1 FROM execution_store.tasks WHERE id=p_task FOR UPDATE;
    RETURN t;
END $$;

CREATE FUNCTION execution_store.read_result(p_task bigint)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,pg_temp AS $$
DECLARE a execution_authority.identities; t execution_store.tasks; c execution_store.commits;
BEGIN
    a := execution_authority.actor('read');
    SELECT * INTO t FROM execution_store.tasks WHERE id=p_task;
    IF NOT FOUND OR t.control_plane <> a.control_plane THEN
        RAISE EXCEPTION 'task unavailable in this domain' USING ERRCODE='42501';
    END IF;
    SELECT * INTO c FROM execution_store.commits WHERE task_id=p_task;
    RETURN jsonb_build_object('task',to_jsonb(t),'commit',CASE WHEN c.task_id IS NULL THEN NULL ELSE to_jsonb(c) END);
END $$;

CREATE FUNCTION execution_store.claim(p_task bigint, p_execution bigint, p_content text, p_release text, p_seconds integer)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,pg_temp AS $$
DECLARE t execution_store.tasks; lease execution_store.leases; attempt execution_store.attempts;
BEGIN
    t := execution_store.lock_task(p_task,p_execution,p_content,p_release);
    IF p_seconds IS NULL OR p_seconds NOT BETWEEN 1 AND 3600 THEN RAISE EXCEPTION 'lease must be 1..3600 seconds'; END IF;
    IF EXISTS (SELECT 1 FROM execution_store.commits WHERE task_id=p_task) THEN
        RETURN jsonb_build_object('status','committed');
    END IF;
    SELECT * INTO lease FROM execution_store.leases WHERE task_id=p_task;
    IF FOUND AND lease.expires_at > clock_timestamp() THEN
        RETURN jsonb_build_object('status','busy','expires_at',lease.expires_at);
    END IF;
    IF lease.task_id IS NOT NULL THEN
        UPDATE execution_store.attempts SET status='failed',reason='lease_expired',finished_at=clock_timestamp()
            WHERE id=lease.attempt_id AND status='running';
    END IF;
    INSERT INTO execution_store.attempts (task_id,authority_execution,fence,status)
        VALUES (p_task,p_execution,COALESCE(lease.fence,0)+1,'running') RETURNING * INTO attempt;
    INSERT INTO execution_store.leases (task_id,attempt_id,fence,expires_at)
        VALUES (p_task,attempt.id,attempt.fence,clock_timestamp()+make_interval(secs=>p_seconds))
        ON CONFLICT (task_id) DO UPDATE SET attempt_id=EXCLUDED.attempt_id,fence=EXCLUDED.fence,expires_at=EXCLUDED.expires_at;
    RETURN jsonb_build_object('status','claimed','attempt',to_jsonb(attempt),'task',to_jsonb(t));
END $$;

CREATE FUNCTION execution_store.live_attempt(p_task bigint, p_attempt uuid, p_execution bigint, p_content text, p_release text)
RETURNS void LANGUAGE plpgsql
SET search_path=pg_catalog,pg_temp AS $$
BEGIN
    PERFORM execution_store.lock_task(p_task,p_execution,p_content,p_release);
    IF NOT EXISTS (SELECT 1 FROM execution_store.leases l JOIN execution_store.attempts a ON a.id=l.attempt_id
        WHERE l.task_id=p_task AND a.id=p_attempt AND a.authority_execution=p_execution
        AND a.fence=l.fence AND a.status='running' AND l.expires_at > clock_timestamp()) THEN
        RAISE EXCEPTION 'attempt expired or fenced' USING ERRCODE='42501';
    END IF;
END $$;

CREATE FUNCTION execution_store.renew(p_task bigint, p_attempt uuid, p_execution bigint, p_content text, p_release text, p_seconds integer)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,pg_temp AS $$
BEGIN
    PERFORM execution_store.live_attempt(p_task,p_attempt,p_execution,p_content,p_release);
    IF p_seconds IS NULL OR p_seconds NOT BETWEEN 1 AND 3600 THEN RAISE EXCEPTION 'lease must be 1..3600 seconds'; END IF;
    UPDATE execution_store.leases SET expires_at=clock_timestamp()+make_interval(secs=>p_seconds) WHERE task_id=p_task;
END $$;

CREATE FUNCTION execution_store.fail(p_task bigint, p_attempt uuid, p_execution bigint, p_content text, p_release text, p_reason text)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,pg_temp AS $$
BEGIN
    PERFORM execution_store.live_attempt(p_task,p_attempt,p_execution,p_content,p_release);
    IF p_reason IS NULL OR length(p_reason) NOT BETWEEN 1 AND 1000 THEN RAISE EXCEPTION 'failure reason required'; END IF;
    UPDATE execution_store.attempts SET status='failed',reason=p_reason,finished_at=clock_timestamp() WHERE id=p_attempt;
    UPDATE execution_store.leases SET expires_at=clock_timestamp() WHERE task_id=p_task;
END $$;

CREATE FUNCTION execution_store.commit_result(p_task bigint, p_attempt uuid, p_execution bigint, p_content text, p_release text, p_sha256 text, p_size bigint)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,pg_temp AS $$
DECLARE existing execution_store.commits;
BEGIN
    PERFORM execution_store.lock_task(p_task,p_execution,p_content,p_release);
    SELECT * INTO existing FROM execution_store.commits WHERE task_id=p_task;
    IF FOUND THEN
        IF existing.attempt_id IS DISTINCT FROM p_attempt OR existing.artifact_sha256 IS DISTINCT FROM p_sha256 OR existing.artifact_size IS DISTINCT FROM p_size THEN
            RAISE EXCEPTION 'immutable commit conflict' USING ERRCODE='23505';
        END IF;
        RETURN;
    END IF;
    PERFORM execution_store.live_attempt(p_task,p_attempt,p_execution,p_content,p_release);
    INSERT INTO execution_store.commits (task_id,attempt_id,artifact_sha256,artifact_size) VALUES (p_task,p_attempt,p_sha256,p_size);
    UPDATE execution_store.attempts SET status='completed',finished_at=clock_timestamp() WHERE id=p_attempt;
END $$;
REVOKE ALL ON ALL TABLES IN SCHEMA execution_store FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA execution_store FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA execution_store FROM PUBLIC;
