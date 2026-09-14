-- Bounded index of immutable, actually authorized request task specifications.
-- No new external authority or entry point. Every transition still reauthorizes
-- under the original request lock; only repeated full-payload scans are removed.
CREATE TABLE execution_store.request_plan_index (
    request_id bigint PRIMARY KEY REFERENCES execution_authority.requests(id),
    schema_version text NOT NULL CHECK(schema_version IN ('execution-plan.v1','execution-plan.v2'))
);
CREATE TABLE execution_store.request_task_specs (
    request_id bigint NOT NULL REFERENCES execution_store.request_plan_index(request_id),
    business_key text NOT NULL,
    task_digest text NOT NULL,
    spec jsonb NOT NULL CHECK(jsonb_typeof(spec)='object'),
    PRIMARY KEY(request_id,business_key),
    UNIQUE(request_id,task_digest)
);
CREATE TRIGGER request_plan_index_immutable BEFORE UPDATE OR DELETE ON execution_store.request_plan_index
FOR EACH ROW EXECUTE FUNCTION public.dehps_research_os_reject_immutable_mutation();
CREATE TRIGGER request_task_specs_immutable BEFORE UPDATE OR DELETE ON execution_store.request_task_specs
FOR EACH ROW EXECUTE FUNCTION public.dehps_research_os_reject_immutable_mutation();
REVOKE ALL ON execution_store.request_plan_index,execution_store.request_task_specs FROM PUBLIC;

CREATE FUNCTION execution_store.index_authorized_plan(p_execution bigint,p_content text,p_release text)
RETURNS bigint LANGUAGE plpgsql
SET search_path=pg_catalog,pg_temp AS $$
DECLARE v_request_id bigint; payload jsonb;
BEGIN
    -- This acquires the same actual request lock used by expiry/revocation.
    PERFORM execution_authority.reauthorize(p_execution,p_content,p_release);
    SELECT e.request_id INTO v_request_id FROM execution_authority.executions e WHERE e.id=p_execution;
    IF EXISTS (SELECT 1 FROM execution_store.request_plan_index i WHERE i.request_id=v_request_id) THEN
        RETURN v_request_id;
    END IF;
    SELECT r.payload INTO payload FROM execution_authority.requests r WHERE r.id=v_request_id;
    IF ((payload->>'schema'='execution-plan.v1' AND payload-ARRAY['schema','tasks']='{}'::jsonb)
        OR (payload->>'schema'='execution-plan.v2' AND payload-ARRAY['schema','tasks','canonical']='{}'::jsonb
            AND jsonb_typeof(payload->'canonical')='object')) IS NOT TRUE
        OR jsonb_typeof(payload->'tasks') IS DISTINCT FROM 'array' THEN
        RAISE EXCEPTION 'closed execution plan required' USING ERRCODE='42501';
    END IF;
    INSERT INTO execution_store.request_plan_index VALUES(v_request_id,payload->>'schema');
    INSERT INTO execution_store.request_task_specs
        SELECT v_request_id,spec->>'business_key',spec->>'task_digest',spec FROM jsonb_array_elements(payload->'tasks') spec;
    RETURN v_request_id;
END $$;
REVOKE ALL ON FUNCTION execution_store.index_authorized_plan(bigint,text,text) FROM PUBLIC;

CREATE OR REPLACE FUNCTION execution_store.plan_actor(p_execution bigint,p_content text,p_release text,p_spec jsonb)
RETURNS execution_authority.identities LANGUAGE plpgsql
SET search_path=pg_catalog,pg_temp AS $$
DECLARE a execution_authority.identities; v_request_id bigint;
BEGIN
    v_request_id:=execution_store.index_authorized_plan(p_execution,p_content,p_release);
    a:=execution_authority.actor('execute');
    IF NOT EXISTS (SELECT 1 FROM execution_store.request_task_specs i
        WHERE i.request_id=v_request_id AND i.business_key=p_spec->>'business_key' AND i.spec=p_spec) THEN
        RAISE EXCEPTION 'task outside approved execution plan' USING ERRCODE='42501';
    END IF;
    RETURN a;
END $$;

-- Same immutable admission checks; indexed membership and dependency lookup.
CREATE OR REPLACE FUNCTION execution_store.admit_plan(p_execution bigint,p_content text,p_release text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,pg_temp AS $$
DECLARE a execution_authority.identities; payload jsonb; packet jsonb; item jsonb; v_spec jsonb;
    definition jsonb; manifest jsonb; bindings jsonb:='{}'; v_task_id bigint; parent_id bigint;
    dependency jsonb; parent_keys jsonb; desired bigint[]; actual bigint[]; stored jsonb;
BEGIN
    PERFORM execution_authority.reauthorize(p_execution,p_content,p_release);
    a := execution_authority.actor('execute');
    SELECT r.payload INTO payload FROM execution_authority.requests r
        JOIN execution_authority.executions e ON e.request_id=r.id WHERE e.id=p_execution;
    IF payload->>'schema' IS DISTINCT FROM 'execution-plan.v2' THEN RAISE EXCEPTION 'canonical plan v2 required'; END IF;
    PERFORM execution_store.plan_actor(p_execution,p_content,p_release,payload->'tasks'->0);
    packet:=payload->'canonical'; manifest:=packet->'manifest';
    SELECT jsonb_object_agg(v->'value'->>'task_key',v->>'digest') INTO parent_keys
        FROM jsonb_array_elements(packet->'tasks') v;
    FOR item IN SELECT * FROM jsonb_array_elements(packet->'goals') LOOP
        definition:=item->'value';
        INSERT INTO public.research_os_goal_definitions(goal_digest,goal_key,semantic_version,objective_class,owner_lane,definition_json)
            VALUES(item->>'digest',definition->>'goal_key',definition->>'semantic_version',definition->>'objective_class',definition->>'owner_lane',definition)
            ON CONFLICT(goal_digest) DO NOTHING;
        SELECT definition_json INTO stored FROM public.research_os_goal_definitions WHERE goal_digest=item->>'digest';
        IF stored IS DISTINCT FROM definition THEN RAISE EXCEPTION 'immutable goal conflict'; END IF;
    END LOOP;
    FOR item IN SELECT * FROM jsonb_array_elements(packet->'tasks') LOOP
        definition:=item->'value';
        INSERT INTO public.research_os_task_definitions(task_digest,task_key,goal_digest,task_type,lane,priority,definition_json)
            VALUES(item->>'digest',definition->>'task_key',definition->>'goal_digest',definition->>'task_type',definition->>'lane',(definition->>'priority')::integer,definition)
            ON CONFLICT(task_digest) DO NOTHING;
        SELECT definition_json INTO stored FROM public.research_os_task_definitions WHERE task_digest=item->>'digest';
        IF stored IS DISTINCT FROM definition THEN RAISE EXCEPTION 'immutable task conflict'; END IF;
    END LOOP;
    INSERT INTO public.research_os_manifests(manifest_digest,schema_version,manifest_json,source)
        VALUES(manifest->>'digest',manifest->'value'->>'schema_version',manifest->'value','execution-plan.v2') ON CONFLICT(manifest_digest) DO NOTHING;
    SELECT manifest_json INTO stored FROM public.research_os_manifests WHERE manifest_digest=manifest->>'digest';
    IF stored IS DISTINCT FROM manifest->'value' THEN RAISE EXCEPTION 'immutable manifest conflict'; END IF;
    INSERT INTO public.research_os_manifest_goals(manifest_digest,goal_digest,ordinal)
        SELECT manifest->>'digest',value->>'digest',ordinality-1 FROM jsonb_array_elements(packet->'goals') WITH ORDINALITY ON CONFLICT DO NOTHING;
    INSERT INTO public.research_os_manifest_tasks(manifest_digest,task_digest,ordinal)
        SELECT manifest->>'digest',value->>'digest',ordinality-1 FROM jsonb_array_elements(packet->'tasks') WITH ORDINALITY ON CONFLICT DO NOTHING;
    INSERT INTO public.research_os_control_planes(control_plane_key,schema_version,current_manifest_digest,source)
        VALUES(a.control_plane,manifest->'value'->>'schema_version',manifest->>'digest','execution-plan.v2') ON CONFLICT DO NOTHING;
    INSERT INTO execution_store.plans VALUES(a.control_plane,manifest->>'digest',payload) ON CONFLICT DO NOTHING;
    SELECT plans.payload INTO stored FROM execution_store.plans WHERE control_plane=a.control_plane AND manifest_digest=manifest->>'digest';
    IF stored IS DISTINCT FROM payload THEN RAISE EXCEPTION 'immutable plan conflict'; END IF;
    FOR v_spec IN SELECT * FROM jsonb_array_elements(payload->'tasks') LOOP
        v_task_id:=NULL;
        -- Completed prior-release bindings may be consumed by a newer plan;
        -- claim/commit still require their original release authorization.
        SELECT t.id INTO v_task_id FROM execution_store.tasks t JOIN execution_store.commits c ON c.task_id=t.id
            WHERE t.control_plane=a.control_plane AND t.business_key=v_spec->>'business_key' AND t.spec=v_spec;
        IF v_task_id IS NULL THEN v_task_id:=execution_store.register_task(p_execution,p_content,p_release,v_spec); END IF;
    END LOOP;
    SELECT jsonb_object_agg(s->>'task_digest',t.id) INTO bindings FROM jsonb_array_elements(payload->'tasks') s
        JOIN execution_store.tasks t ON t.control_plane=a.control_plane AND t.business_key=s->>'business_key' AND t.spec=s;
    FOR item IN SELECT * FROM jsonb_array_elements(packet->'tasks') LOOP
        v_task_id:=(bindings->>(item->>'digest'))::bigint; desired:=ARRAY[]::bigint[];
        FOR dependency IN SELECT * FROM jsonb_array_elements(item->'value'->'dependencies') WHERE value->>'dependency_type'='task' LOOP
            parent_id:=(bindings->>(parent_keys->>(dependency->>'target_key')))::bigint;
            IF parent_id IS NULL THEN RAISE EXCEPTION 'canonical dependency binding missing'; END IF;
            desired:=array_append(desired,parent_id);
            INSERT INTO execution_store.task_inputs VALUES(v_task_id,parent_id) ON CONFLICT DO NOTHING;
        END LOOP;
        SELECT COALESCE(array_agg(parent_task_id ORDER BY parent_task_id),ARRAY[]::bigint[]) INTO actual FROM execution_store.task_inputs i WHERE i.task_id=v_task_id;
        SELECT COALESCE(array_agg(v ORDER BY v),ARRAY[]::bigint[]) INTO desired FROM unnest(desired) v;
        IF actual IS DISTINCT FROM desired THEN RAISE EXCEPTION 'immutable dependency binding conflict'; END IF;
    END LOOP;
    -- Even an all-completed reused plan must not write admission records after
    -- expiry while its large canonical packet is being checked.
    PERFORM execution_authority.reauthorize(p_execution,p_content,p_release);
    RETURN bindings;
END $$;

CREATE OR REPLACE FUNCTION execution_store.read_plan(p_manifest text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,pg_temp AS $$
DECLARE a execution_authority.identities; payload jsonb; bindings jsonb;
BEGIN
    a:=execution_authority.actor('read');
    SELECT plans.payload INTO payload FROM execution_store.plans WHERE control_plane=a.control_plane AND manifest_digest=p_manifest;
    IF NOT FOUND THEN RAISE EXCEPTION 'plan unavailable' USING ERRCODE='42501'; END IF;
    SELECT jsonb_object_agg(entries.value->>'task_digest',t.id) INTO bindings FROM jsonb_array_elements(payload->'tasks') AS entries(value)
        JOIN execution_store.tasks t ON t.control_plane=a.control_plane AND t.business_key=entries.value->>'business_key' AND t.spec=entries.value;
    RETURN jsonb_build_object('payload',payload,'bindings',bindings);
END $$;
