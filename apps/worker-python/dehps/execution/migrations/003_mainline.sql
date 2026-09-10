-- Add canonical intake/registration to 001/002, with the same NOLOGIN owner.
CREATE TABLE execution_store.plans (
    control_plane text NOT NULL REFERENCES public.research_os_control_planes(control_plane_key),
    manifest_digest text NOT NULL REFERENCES public.research_os_manifests(manifest_digest),
    payload jsonb NOT NULL,
    PRIMARY KEY (control_plane,manifest_digest)
);
CREATE TABLE execution_store.task_inputs (
    task_id bigint NOT NULL REFERENCES execution_store.tasks(id),
    parent_task_id bigint NOT NULL REFERENCES execution_store.tasks(id),
    PRIMARY KEY(task_id,parent_task_id),
    CHECK(task_id<>parent_task_id)
);
CREATE TRIGGER execution_plans_immutable BEFORE UPDATE OR DELETE ON execution_store.plans
FOR EACH ROW EXECUTE FUNCTION public.dehps_research_os_reject_immutable_mutation();
CREATE TRIGGER execution_inputs_immutable BEFORE UPDATE OR DELETE ON execution_store.task_inputs
FOR EACH ROW EXECUTE FUNCTION public.dehps_research_os_reject_immutable_mutation();

CREATE OR REPLACE FUNCTION execution_store.plan_actor(p_execution bigint, p_content text, p_release text, p_spec jsonb)
RETURNS execution_authority.identities LANGUAGE plpgsql
SET search_path=pg_catalog,pg_temp AS $$
DECLARE a execution_authority.identities; payload jsonb;
BEGIN
    PERFORM execution_authority.reauthorize(p_execution,p_content,p_release);
    a := execution_authority.actor('execute');
    SELECT r.payload INTO payload FROM execution_authority.requests r
        JOIN execution_authority.executions e ON e.request_id=r.id WHERE e.id=p_execution;
    IF ((payload->>'schema'='execution-plan.v1' AND payload-ARRAY['schema','tasks']='{}'::jsonb)
        OR (payload->>'schema'='execution-plan.v2' AND payload-ARRAY['schema','tasks','canonical']='{}'::jsonb
            AND jsonb_typeof(payload->'canonical')='object')) IS NOT TRUE
        OR jsonb_typeof(payload->'tasks') IS DISTINCT FROM 'array' THEN
        RAISE EXCEPTION 'closed execution plan required' USING ERRCODE='42501';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM jsonb_array_elements(payload->'tasks') entry WHERE entry=p_spec) THEN
        RAISE EXCEPTION 'task outside approved execution plan' USING ERRCODE='42501';
    END IF;
    RETURN a;
END $$;

CREATE FUNCTION execution_store.admit_plan(p_execution bigint,p_content text,p_release text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,pg_temp AS $$
DECLARE a execution_authority.identities; payload jsonb; packet jsonb; item jsonb; v_spec jsonb;
    definition jsonb; manifest jsonb; bindings jsonb:='{}'; v_task_id bigint; parent_id bigint;
    dependency jsonb; parent_spec jsonb; desired bigint[]; actual bigint[]; stored jsonb;
BEGIN
    PERFORM execution_authority.reauthorize(p_execution,p_content,p_release);
    a := execution_authority.actor('execute');
    SELECT r.payload INTO payload FROM execution_authority.requests r
        JOIN execution_authority.executions e ON e.request_id=r.id WHERE e.id=p_execution;
    IF payload->>'schema' IS DISTINCT FROM 'execution-plan.v2' THEN RAISE EXCEPTION 'canonical plan v2 required'; END IF;
    PERFORM execution_store.plan_actor(p_execution,p_content,p_release,payload->'tasks'->0);
    packet:=payload->'canonical'; manifest:=packet->'manifest';
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
        PERFORM execution_store.plan_actor(p_execution,p_content,p_release,v_spec);
        v_task_id:=NULL;
        -- Completed prior-release bindings may be consumed by a newer plan;
        -- claim/commit still require their original release authorization.
        SELECT t.id INTO v_task_id FROM execution_store.tasks t JOIN execution_store.commits c ON c.task_id=t.id
            WHERE t.control_plane=a.control_plane AND t.business_key=v_spec->>'business_key' AND t.spec=v_spec;
        IF v_task_id IS NULL THEN v_task_id:=execution_store.register_task(p_execution,p_content,p_release,v_spec); END IF;
        bindings:=bindings||jsonb_build_object(v_spec->>'task_digest',v_task_id);
    END LOOP;
    FOR item IN SELECT * FROM jsonb_array_elements(packet->'tasks') LOOP
        v_task_id:=(bindings->>(item->>'digest'))::bigint; desired:=ARRAY[]::bigint[];
        FOR dependency IN SELECT * FROM jsonb_array_elements(item->'value'->'dependencies') WHERE value->>'dependency_type'='task' LOOP
            SELECT spec_item INTO parent_spec FROM jsonb_array_elements(payload->'tasks') spec_item
                JOIN jsonb_array_elements(packet->'tasks') parent ON parent->>'digest'=spec_item->>'task_digest'
                WHERE parent->'value'->>'task_key'=dependency->>'target_key';
            parent_id:=(bindings->>(parent_spec->>'task_digest'))::bigint;
            IF parent_id IS NULL THEN RAISE EXCEPTION 'canonical dependency binding missing'; END IF;
            desired:=array_append(desired,parent_id);
            INSERT INTO execution_store.task_inputs VALUES(v_task_id,parent_id) ON CONFLICT DO NOTHING;
        END LOOP;
        SELECT COALESCE(array_agg(parent_task_id ORDER BY parent_task_id),ARRAY[]::bigint[]) INTO actual FROM execution_store.task_inputs i WHERE i.task_id=v_task_id;
        SELECT COALESCE(array_agg(v ORDER BY v),ARRAY[]::bigint[]) INTO desired FROM unnest(desired) v;
        IF actual IS DISTINCT FROM desired THEN RAISE EXCEPTION 'immutable dependency binding conflict'; END IF;
    END LOOP;
    RETURN bindings;
END $$;

CREATE FUNCTION execution_store.read_plan(p_manifest text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,pg_temp AS $$
DECLARE a execution_authority.identities; payload jsonb; bindings jsonb;
BEGIN
    a:=execution_authority.actor('read');
    SELECT plans.payload INTO payload FROM execution_store.plans WHERE control_plane=a.control_plane AND manifest_digest=p_manifest;
    IF NOT FOUND THEN RAISE EXCEPTION 'plan unavailable' USING ERRCODE='42501'; END IF;
    SELECT jsonb_object_agg(entries.value->>'task_digest',t.id) INTO bindings FROM jsonb_array_elements(payload->'tasks') AS entries(value)
        JOIN execution_store.tasks t ON t.control_plane=a.control_plane AND t.spec=entries.value;
    RETURN jsonb_build_object('payload',payload,'bindings',bindings);
END $$;

CREATE FUNCTION execution_store.mainline_context(p_task bigint)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,pg_temp AS $$
DECLARE snapshot jsonb; attempt execution_store.attempts; execution text; parents jsonb; records jsonb; definition jsonb;
BEGIN
    snapshot:=execution_store.read_result(p_task);
    SELECT definition_json INTO definition FROM public.research_os_task_definitions WHERE task_digest=snapshot->'task'->>'task_digest';
    SELECT a.* INTO attempt FROM execution_store.attempts a JOIN execution_store.commits c ON c.attempt_id=a.id WHERE c.task_id=p_task;
    execution:=encode(sha256(uuid_send(attempt.id)),'hex');
    SELECT COALESCE(jsonb_agg(jsonb_build_object('task_id',i.parent_task_id,'commit',CASE WHEN c.task_id IS NULL THEN NULL ELSE to_jsonb(c) END) ORDER BY i.parent_task_id),'[]'::jsonb)
        INTO parents FROM execution_store.task_inputs i LEFT JOIN execution_store.commits c ON c.task_id=i.parent_task_id WHERE i.task_id=p_task;
    records:=jsonb_build_object(
        'started',(SELECT jsonb_build_object('digest',event_digest,'value',event_json) FROM public.research_os_mainline_execution_events WHERE execution_id=execution AND event_type='started'),
        'completed',(SELECT jsonb_build_object('digest',event_digest,'value',event_json) FROM public.research_os_mainline_execution_events WHERE execution_id=execution AND event_type='completed'),
        'registration',(SELECT jsonb_build_object('digest',registration_digest,'value',registration_json) FROM public.research_os_mainline_artifacts WHERE execution_id=execution));
    RETURN snapshot||jsonb_build_object('definition',definition,'attempt',CASE WHEN attempt.id IS NULL THEN NULL ELSE to_jsonb(attempt) END,'parents',parents,'records',records,
        'event_count',(SELECT count(*) FROM public.research_os_mainline_execution_events WHERE execution_id=execution),
        'registration_count',(SELECT count(*) FROM public.research_os_mainline_artifacts WHERE execution_id=execution));
END $$;

-- This canonicalizer is deliberately limited to runtime record values (integer
-- sizes/sequences, strings, arrays, objects). It cannot hash scientific floats.
-- It retains the existing Python Mainline* envelope/digest algorithm.
CREATE FUNCTION execution_store.record_json_v1(value jsonb)
RETURNS text LANGUAGE plpgsql IMMUTABLE STRICT
SET search_path=pg_catalog,pg_temp AS $$
DECLARE result text;
BEGIN
    CASE jsonb_typeof(value)
    WHEN 'object' THEN
        SELECT '{'||COALESCE(string_agg(to_jsonb(key)::text||':'||execution_store.record_json_v1(item),',' ORDER BY key COLLATE "C"),'')||'}'
            INTO result FROM jsonb_each(value) AS entries(key,item);
    WHEN 'array' THEN
        SELECT '['||COALESCE(string_agg(execution_store.record_json_v1(item),',' ORDER BY ordinal),'')||']'
            INTO result FROM jsonb_array_elements(value) WITH ORDINALITY AS entries(item,ordinal);
    WHEN 'number' THEN
        IF value::text !~ '^-?(0|[1-9][0-9]*)$' THEN RAISE EXCEPTION 'runtime record requires integer numeric values'; END IF;
        result:=value::text;
    ELSE result:=value::text;
    END CASE;
    RETURN result;
END $$;

CREATE FUNCTION execution_store.record_digest_v1(kind text,value jsonb)
RETURNS text LANGUAGE plpgsql IMMUTABLE STRICT
SET search_path=pg_catalog,pg_temp AS $$
DECLARE envelope jsonb; canonical text; escaped text:=''; letter text; code integer; position integer;
BEGIN
    IF kind NOT IN ('event','registration') THEN RAISE EXCEPTION 'unsupported runtime record'; END IF;
    envelope:=jsonb_build_object('schema','research-os-control-plane-v1',
        'artifact_type',CASE WHEN kind='event' THEN 'mainline_execution_event' ELSE 'mainline_artifact_registration' END,kind,value);
    canonical:=execution_store.record_json_v1(envelope);
    -- Legacy stable_json uses ensure_ascii=True, including UTF-16 surrogate
    -- pairs for supplementary characters and an escape for ASCII DEL.
    FOR position IN 1..length(canonical) LOOP
        letter:=substr(canonical,position,1); code:=ascii(letter);
        IF code<127 THEN escaped:=escaped||letter;
        ELSIF code<=65535 THEN escaped:=escaped||chr(92)||'u'||lpad(to_hex(code),4,'0');
        ELSE
            escaped:=escaped||chr(92)||'u'||to_hex(55296+((code-65536)>>10))||chr(92)||'u'||to_hex(56320+((code-65536)&1023));
        END IF;
    END LOOP;
    RETURN encode(sha256(convert_to(escaped,'UTF8')),'hex');
END $$;

CREATE FUNCTION execution_store.record_mainline(p_task bigint,p_execution bigint,p_content text,p_release text,p_records jsonb)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,pg_temp AS $$
DECLARE t execution_store.tasks; c execution_store.commits; a execution_store.attempts;
    definition jsonb; execution text; common jsonb; expected jsonb; entry jsonb; label text; seq integer;
    instant timestamptz; parents jsonb; payload jsonb; context jsonb;
BEGIN
    t:=execution_store.lock_task(p_task,p_execution,p_content,p_release);
    SELECT * INTO c FROM execution_store.commits WHERE task_id=p_task;
    IF NOT FOUND THEN RAISE EXCEPTION 'committed task required'; END IF;
    SELECT * INTO a FROM execution_store.attempts WHERE id=c.attempt_id;
    SELECT definition_json INTO definition FROM public.research_os_task_definitions WHERE task_digest=t.task_digest;
    execution:=encode(sha256(uuid_send(a.id)),'hex');
    IF EXISTS (SELECT 1 FROM execution_store.task_inputs i LEFT JOIN execution_store.commits pc ON pc.task_id=i.parent_task_id
        WHERE i.task_id=p_task AND (pc.task_id IS NULL OR pc.created_at>a.created_at OR NOT EXISTS
            (SELECT 1 FROM public.research_os_mainline_execution_events e WHERE e.execution_id=encode(sha256(uuid_send(pc.attempt_id)),'hex') AND e.event_type='completed'))) THEN
        RAISE EXCEPTION 'parent mainline result was not available at attempt start';
    END IF;
    SELECT COALESCE(jsonb_agg(digest ORDER BY digest),'[]'::jsonb) INTO parents FROM
        (SELECT value AS digest FROM jsonb_array_elements_text(definition->'input_artifact_digests')
         UNION SELECT pc.artifact_sha256 FROM execution_store.task_inputs i JOIN execution_store.commits pc ON pc.task_id=i.parent_task_id WHERE i.task_id=p_task) all_parents;
    expected:=jsonb_build_object('execution_id',execution,'control_plane_key',t.control_plane,'task_key',definition->>'task_key','task_digest',t.task_digest,
        'artifact_digest',c.artifact_sha256,'artifact_type','execution-result','schema_version',t.artifact_schema,
        'artifact_path',t.control_plane||'/artifacts/objects/'||c.artifact_sha256||'.blob','parent_digests',parents,'git_commit','');
    IF p_records->'registration'->'value' IS DISTINCT FROM expected OR p_records-ARRAY['started','completed','registration']<>'{}'::jsonb THEN RAISE EXCEPTION 'canonical registration binding mismatch'; END IF;
    common:=jsonb_build_object('execution_id',execution,'control_plane_key',t.control_plane,'task_key',definition->>'task_key','task_digest',t.task_digest,
        'manifest_digest',t.manifest_digest,'capability',definition->>'requested_capability');
    payload:=jsonb_build_array(jsonb_build_array('artifact_schema',t.artifact_schema),jsonb_build_array('artifact_sha256',c.artifact_sha256),
        jsonb_build_array('artifact_size',c.artifact_size),jsonb_build_array('release_sha256',t.release_sha256),
        jsonb_build_array('scientific_contract_sha256',t.scientific_contract_sha256),jsonb_build_array('verifier_id',t.verifier_id));
    FOREACH label IN ARRAY ARRAY['started','completed'] LOOP
        seq:=CASE WHEN label='started' THEN 0 ELSE 1 END;
        instant:=CASE WHEN label='started' THEN a.created_at ELSE c.created_at END;
        entry:=p_records->label;
        IF entry->>'digest' IS DISTINCT FROM execution_store.record_digest_v1('event',entry->'value') THEN RAISE EXCEPTION 'canonical event digest mismatch'; END IF;
        expected:=common||jsonb_build_object('event_type',label,'sequence',seq,'payload',CASE WHEN label='started' THEN '[]'::jsonb ELSE payload END);
        IF (entry->'value')-'recorded_at' IS DISTINCT FROM expected OR (entry->'value'->>'recorded_at')::timestamptz IS DISTINCT FROM instant THEN RAISE EXCEPTION 'canonical event binding mismatch'; END IF;
        INSERT INTO public.research_os_mainline_execution_events(event_digest,execution_id,control_plane_key,manifest_digest,task_digest,task_key,capability,event_type,sequence,recorded_at,event_json)
            VALUES(entry->>'digest',execution,t.control_plane,t.manifest_digest,t.task_digest,definition->>'task_key',definition->>'requested_capability',label,seq,instant,entry->'value') ON CONFLICT(event_digest) DO NOTHING;
    END LOOP;
    entry:=p_records->'registration';
    IF entry->>'digest' IS DISTINCT FROM execution_store.record_digest_v1('registration',entry->'value') THEN RAISE EXCEPTION 'canonical registration digest mismatch'; END IF;
    INSERT INTO public.research_os_mainline_artifacts(registration_digest,execution_id,control_plane_key,task_digest,task_key,artifact_digest,artifact_type,schema_version,artifact_path,parent_digests_json,git_commit,registration_json)
        VALUES(entry->>'digest',execution,t.control_plane,t.task_digest,definition->>'task_key',c.artifact_sha256,'execution-result',t.artifact_schema,
            t.control_plane||'/artifacts/objects/'||c.artifact_sha256||'.blob',parents,'',entry->'value') ON CONFLICT(registration_digest) DO NOTHING;
    context:=execution_store.mainline_context(p_task);
    IF context->'records' IS DISTINCT FROM p_records OR context->>'event_count'<>'2' OR context->>'registration_count'<>'1' THEN RAISE EXCEPTION 'immutable canonical record conflict'; END IF;
END $$;
REVOKE ALL ON execution_store.plans,execution_store.task_inputs FROM PUBLIC;
REVOKE ALL ON FUNCTION execution_store.admit_plan(bigint,text,text),execution_store.read_plan(text),execution_store.mainline_context(bigint),execution_store.record_mainline(bigint,bigint,text,text,jsonb) FROM PUBLIC;

REVOKE ALL ON FUNCTION execution_store.record_json_v1(jsonb),execution_store.record_digest_v1(text,jsonb) FROM PUBLIC;
