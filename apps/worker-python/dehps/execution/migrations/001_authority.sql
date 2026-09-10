-- Install once, transactionally, as a dedicated NOLOGIN schema owner. Never
-- install from a runtime client. Administrator provisions identities/grants.
CREATE SCHEMA execution_authority;
REVOKE ALL ON SCHEMA execution_authority FROM PUBLIC;

CREATE TABLE execution_authority.identities (
    login_oid oid PRIMARY KEY,
    login_name name NOT NULL UNIQUE,
    principal text NOT NULL CHECK (length(principal) BETWEEN 1 AND 200),
    control_plane text NOT NULL CHECK (control_plane ~ '^[a-z][a-z0-9-]{0,95}$'),
    can_request boolean NOT NULL DEFAULT false,
    can_review boolean NOT NULL DEFAULT false,
    can_execute boolean NOT NULL DEFAULT false,
    active boolean NOT NULL DEFAULT true
);
CREATE TABLE execution_authority.requests (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    control_plane text NOT NULL,
    requester text NOT NULL,
    login_oid oid NOT NULL,
    login_name name NOT NULL,
    display_label text NOT NULL,
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    content_sha256 text NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    release_sha256 text NOT NULL CHECK (release_sha256 ~ '^[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE execution_authority.approvals (
    request_id bigint PRIMARY KEY REFERENCES execution_authority.requests(id),
    reviewer text NOT NULL,
    login_oid oid NOT NULL,
    login_name name NOT NULL,
    display_label text NOT NULL,
    content_sha256 text NOT NULL,
    release_sha256 text NOT NULL,
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE execution_authority.revocations (
    request_id bigint PRIMARY KEY REFERENCES execution_authority.requests(id),
    principal text NOT NULL,
    login_oid oid NOT NULL,
    login_name name NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE execution_authority.executions (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    request_id bigint NOT NULL UNIQUE REFERENCES execution_authority.approvals(request_id),
    executor text NOT NULL,
    login_oid oid NOT NULL,
    login_name name NOT NULL,
    display_label text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

-- Private helper: caller cannot execute it. Row lock orders administrator
-- revocation against the admission transaction; READ COMMITTED prevents stale
-- snapshots from continuing to authorize after revocation has committed.
CREATE FUNCTION execution_authority.actor(p_action text)
RETURNS execution_authority.identities LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp AS $$
DECLARE a execution_authority.identities;
BEGIN
    IF current_setting('transaction_isolation') <> 'read committed' THEN
        RAISE EXCEPTION 'authority requires read committed' USING ERRCODE = '42501';
    END IF;
    SELECT i.* INTO a FROM execution_authority.identities i
        JOIN pg_catalog.pg_roles r ON r.oid = i.login_oid AND r.rolname = i.login_name
        WHERE i.login_name = session_user AND i.active
        AND NOT (r.rolsuper OR r.rolcreatedb OR r.rolcreaterole OR r.rolbypassrls)
        FOR SHARE OF i;
    IF NOT FOUND OR NOT (CASE p_action
        WHEN 'request' THEN a.can_request WHEN 'review' THEN a.can_review
        WHEN 'execute' THEN a.can_execute WHEN 'read' THEN true ELSE false END) THEN
        RAISE EXCEPTION 'authenticated principal not authorized' USING ERRCODE = '42501';
    END IF;
    RETURN a;
END $$;

CREATE FUNCTION execution_authority.request_create(p_payload jsonb, p_release text, p_label text)
RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp AS $$
DECLARE a execution_authority.identities; result bigint;
BEGIN
    a := execution_authority.actor('request');
    INSERT INTO execution_authority.requests
        (control_plane, requester, login_oid, login_name, display_label, payload, content_sha256, release_sha256)
    VALUES (a.control_plane, a.principal, a.login_oid, a.login_name, p_label, p_payload,
        encode(sha256(convert_to(p_payload::text, 'UTF8')), 'hex'), p_release)
    RETURNING id INTO result;
    RETURN result;
END $$;

CREATE FUNCTION execution_authority.request_get(p_request bigint)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp AS $$
DECLARE a execution_authority.identities; r execution_authority.requests;
BEGIN
    a := execution_authority.actor('read');
    SELECT * INTO r FROM execution_authority.requests WHERE id = p_request;
    IF NOT FOUND OR r.control_plane <> a.control_plane THEN
        RAISE EXCEPTION 'request unavailable in this control domain' USING ERRCODE = '42501';
    END IF;
    RETURN to_jsonb(r);
END $$;

CREATE FUNCTION execution_authority.approve(p_request bigint, p_content text, p_release text,
    p_expires timestamptz, p_label text)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp AS $$
DECLARE a execution_authority.identities; r execution_authority.requests;
BEGIN
    a := execution_authority.actor('review');
    SELECT * INTO r FROM execution_authority.requests WHERE id = p_request FOR UPDATE;
    IF NOT FOUND OR r.control_plane <> a.control_plane OR r.requester = a.principal
        OR p_content IS DISTINCT FROM r.content_sha256 OR p_release IS DISTINCT FROM r.release_sha256
        OR p_expires IS NULL OR NOT isfinite(p_expires) OR p_expires <= clock_timestamp()
        OR EXISTS (SELECT 1 FROM execution_authority.revocations WHERE request_id = p_request)
        OR EXISTS (SELECT 1 FROM execution_authority.executions WHERE request_id = p_request AND executor = a.principal)
    THEN
        RAISE EXCEPTION 'independent bound approval required' USING ERRCODE = '42501';
    END IF;
    INSERT INTO execution_authority.approvals
        (request_id, reviewer, login_oid, login_name, display_label, content_sha256, release_sha256, expires_at)
    VALUES (p_request, a.principal, a.login_oid, a.login_name, p_label, p_content, p_release, p_expires);
END $$;

CREATE FUNCTION execution_authority.revoke(p_request bigint)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp AS $$
DECLARE a execution_authority.identities; r execution_authority.requests;
BEGIN
    a := execution_authority.actor('review');
    SELECT * INTO r FROM execution_authority.requests WHERE id = p_request FOR UPDATE;
    IF NOT FOUND OR r.control_plane <> a.control_plane THEN
        RAISE EXCEPTION 'request unavailable in this control domain' USING ERRCODE = '42501';
    END IF;
    INSERT INTO execution_authority.revocations (request_id, principal, login_oid, login_name)
        VALUES (p_request, a.principal, a.login_oid, a.login_name);
END $$;

-- Private shared validator, used both at first admission and by the execution
-- store on resume/commit. The request lock serializes starts with revocation.
CREATE FUNCTION execution_authority.check_execution(p_request bigint, p_content text, p_release text)
RETURNS execution_authority.identities LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp AS $$
DECLARE a execution_authority.identities; r execution_authority.requests;
    approval execution_authority.approvals;
BEGIN
    a := execution_authority.actor('execute');
    SELECT * INTO r FROM execution_authority.requests WHERE id = p_request FOR UPDATE;
    IF NOT FOUND OR r.control_plane <> a.control_plane
        OR p_content IS DISTINCT FROM r.content_sha256 OR p_release IS DISTINCT FROM r.release_sha256
        OR EXISTS (SELECT 1 FROM execution_authority.revocations WHERE request_id = p_request)
    THEN
        RAISE EXCEPTION 'execution binding invalid or revoked' USING ERRCODE = '42501';
    END IF;
    SELECT * INTO approval FROM execution_authority.approvals WHERE request_id = p_request;
    IF NOT FOUND OR approval.reviewer = a.principal OR approval.reviewer = r.requester
        OR approval.content_sha256 <> r.content_sha256 OR approval.release_sha256 <> r.release_sha256
        OR approval.expires_at <= clock_timestamp()
    THEN
        RAISE EXCEPTION 'valid independent approval required' USING ERRCODE = '42501';
    END IF;
    PERFORM 1 FROM execution_authority.identities i JOIN pg_catalog.pg_roles role
        ON role.oid = i.login_oid AND role.rolname = i.login_name
        WHERE i.login_oid = approval.login_oid AND i.login_name = approval.login_name
        AND i.principal = approval.reviewer AND i.control_plane = r.control_plane
        AND i.active AND i.can_review
        AND NOT (role.rolsuper OR role.rolcreatedb OR role.rolcreaterole OR role.rolbypassrls)
        FOR SHARE OF i;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'reviewer authority no longer valid' USING ERRCODE = '42501';
    END IF;
    RETURN a;
END $$;

CREATE FUNCTION execution_authority.begin_execution(p_request bigint, p_content text, p_release text, p_label text)
RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp AS $$
DECLARE a execution_authority.identities; e execution_authority.executions;
BEGIN
    a := execution_authority.check_execution(p_request, p_content, p_release);
    SELECT * INTO e FROM execution_authority.executions WHERE request_id = p_request;
    IF FOUND THEN
        IF e.executor <> a.principal OR e.login_oid <> a.login_oid THEN
            RAISE EXCEPTION 'execution belongs to another identity' USING ERRCODE = '42501';
        END IF;
        RETURN e.id;
    END IF;
    INSERT INTO execution_authority.executions (request_id, executor, login_oid, login_name, display_label)
    VALUES (p_request, a.principal, a.login_oid, a.login_name, p_label) RETURNING * INTO e;
    RETURN e.id;
END $$;

CREATE FUNCTION execution_authority.reauthorize(p_execution bigint, p_content text, p_release text)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp AS $$
DECLARE a execution_authority.identities; e execution_authority.executions;
BEGIN
    SELECT * INTO e FROM execution_authority.executions WHERE id = p_execution;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'execution unavailable' USING ERRCODE = '42501';
    END IF;
    a := execution_authority.check_execution(e.request_id, p_content, p_release);
    IF e.executor <> a.principal OR e.login_oid <> a.login_oid THEN
        RAISE EXCEPTION 'execution belongs to another identity' USING ERRCODE = '42501';
    END IF;
END $$;

REVOKE ALL ON ALL TABLES IN SCHEMA execution_authority FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA execution_authority FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA execution_authority FROM PUBLIC;
-- Deliberately no PUBLIC/runtime grants. Provision only the six public entry
-- functions by exact signature, never actor/check_execution or table DML.
