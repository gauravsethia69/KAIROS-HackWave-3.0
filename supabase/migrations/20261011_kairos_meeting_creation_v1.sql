-- KAIROS Pass 10A: narrowly-authorized meeting creation.
-- REVIEW AND APPLY ONLY AFTER BACKUP / PERSON B APPROVAL.
-- No existing meeting rows are changed; introduces a nullable link from calendar
-- reservations to newly created meetings, then one restricted SECURITY DEFINER RPC.
-- Current authenticated meeting-table policies are SELECT-only; direct INSERT
-- grants or broad write RLS policies are deliberately NOT added.
BEGIN;

ALTER TABLE public.employee_schedule_blocks
  ADD COLUMN IF NOT EXISTS meeting_id text REFERENCES public.meetings(id) ON DELETE CASCADE;

CREATE UNIQUE INDEX IF NOT EXISTS kairos_schedule_one_reservation_per_attendee
  ON public.employee_schedule_blocks(meeting_id, employee_id) WHERE meeting_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS kairos_schedule_overlap_lookup
  ON public.employee_schedule_blocks(employee_id, starts_at, ends_at);
CREATE INDEX IF NOT EXISTS kairos_meeting_participant_employee_lookup
  ON public.meeting_participants(employee_id, meeting_id);

ALTER TABLE public.meetings ADD COLUMN IF NOT EXISTS kairos_request_id uuid;
ALTER TABLE public.meetings ADD COLUMN IF NOT EXISTS kairos_payload_hash text;
CREATE UNIQUE INDEX IF NOT EXISTS kairos_meeting_request_id_unique
  ON public.meetings(organizer_employee_id, kairos_request_id)
  WHERE kairos_request_id IS NOT NULL;

CREATE OR REPLACE FUNCTION public.kairos_create_meeting_v1(
    p_title text, p_client_id text, p_project_id text, p_purpose text,
    p_start timestamptz, p_end timestamptz,
    p_requested_employee_ids text[], p_request_id uuid
) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = ''
AS $fn$
DECLARE
    v_organizer text;
    v_attendees text[];
    v_employee text;
    v_meeting_id text;
    v_existing public.meetings%ROWTYPE;
    v_names text;
    v_block_ids text[] := ARRAY[]::text[];
    v_block_id text;
    v_fingerprint text;
    v_now timestamptz := clock_timestamp();
BEGIN
    IF auth.uid() IS NULL THEN
        RAISE EXCEPTION 'Verified employee identity is required' USING ERRCODE = '42501';
    END IF;
    SELECT a.employee_id INTO v_organizer FROM public.employee_access a
      WHERE a.auth_user_id = auth.uid() AND a.account_enabled IS TRUE LIMIT 1;
    IF v_organizer IS NULL THEN
        RAISE EXCEPTION 'Active employee access required' USING ERRCODE = '42501';
    END IF;
    IF p_request_id IS NULL OR p_title IS NULL OR length(btrim(p_title)) NOT BETWEEN 3 AND 160
       OR p_title <> btrim(p_title) OR p_purpose IS NULL OR length(p_purpose) > 800
       OR p_start IS NULL OR p_end IS NULL
       OR p_start < v_now + interval '5 minutes' OR p_start > v_now + interval '365 days'
       OR p_end - p_start < interval '15 minutes' OR p_end - p_start > interval '4 hours' THEN
        RAISE EXCEPTION 'Invalid meeting details' USING ERRCODE = '22023';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM public.clients c WHERE c.id=p_client_id) THEN
        RAISE EXCEPTION 'Unknown client' USING ERRCODE = '22023';
    END IF;
    IF p_project_id IS NOT NULL AND NOT EXISTS (
         SELECT 1 FROM public.projects p WHERE p.id=p_project_id AND p.client_id=p_client_id
    ) THEN
         RAISE EXCEPTION 'Project does not belong to client' USING ERRCODE = '22023';
    END IF;
    IF COALESCE(array_length(p_requested_employee_ids,1),0) > 12 THEN
        RAISE EXCEPTION 'Too many requested participants' USING ERRCODE = '22023';
    END IF;
    SELECT array_agg(employee_id ORDER BY employee_id) INTO v_attendees
      FROM (SELECT DISTINCT unnest(coalesce(p_requested_employee_ids,ARRAY[]::text[]) || ARRAY[v_organizer]) AS employee_id) requested
      WHERE employee_id IS NOT NULL AND employee_id <> '';
    IF coalesce(cardinality(v_attendees),0) < 1 OR cardinality(v_attendees) > 12 OR EXISTS (
        SELECT 1 FROM unnest(v_attendees) attendee
        WHERE NOT EXISTS (SELECT 1 FROM public.employees e WHERE e.id=attendee)
    ) THEN
        RAISE EXCEPTION 'Invalid participant employee' USING ERRCODE = '22023';
    END IF;

    v_fingerprint := md5(concat_ws(chr(31),p_title,p_client_id,coalesce(p_project_id,''),
                     p_purpose,extract(epoch from p_start)::text,extract(epoch from p_end)::text,array_to_string(v_attendees,',')));

    -- Serialize booking actions for the same employees. Other writers must also
    -- use this RPC, or a separate database-level exclusion policy must be added.
    FOREACH v_employee IN ARRAY v_attendees LOOP
        PERFORM pg_catalog.pg_advisory_xact_lock(
            pg_catalog.hashtextextended('kairos:meeting:' || v_employee, 0));
    END LOOP;

    -- Idempotent retries return the already-created meeting instead of duplicating.
    SELECT * INTO v_existing FROM public.meetings m
      WHERE m.organizer_employee_id=v_organizer AND m.kairos_request_id=p_request_id LIMIT 1;
    IF FOUND THEN
        IF v_existing.kairos_payload_hash IS DISTINCT FROM v_fingerprint THEN
           RAISE EXCEPTION 'Request ID reused for a different meeting' USING ERRCODE='22023';
        END IF;
        RETURN jsonb_build_object(
            'id',v_existing.id, 'title',v_existing.title,
            'starts_at',v_existing.starts_at, 'ends_at',v_existing.ends_at,
            'organizer_employee_id',v_organizer, 'participant_employee_ids',v_attendees,
            'replayed',true);
    END IF;

    -- Conservative first pass: block conflicting bookings instead of offering
    -- ranked alternatives, which will be implemented in the next pass.
    IF EXISTS (
        SELECT 1 FROM public.employee_schedule_blocks b
        WHERE b.employee_id = ANY(v_attendees) AND b.starts_at < p_end AND b.ends_at > p_start
    ) OR EXISTS (
        SELECT 1 FROM public.meetings m
        WHERE m.starts_at IS NOT NULL AND m.ends_at IS NOT NULL
          AND m.starts_at < p_end AND m.ends_at > p_start
          AND (m.organizer_employee_id=ANY(v_attendees) OR EXISTS (
              SELECT 1 FROM public.meeting_participants mp
              WHERE mp.meeting_id=m.id AND mp.employee_id=ANY(v_attendees)))
    ) THEN
        RAISE EXCEPTION 'A participant has a recorded overlapping booking' USING ERRCODE='23P01';
    END IF;

    SELECT string_agg(e.full_name, ', ' ORDER BY e.full_name) INTO v_names
      FROM public.employees e WHERE e.id=ANY(v_attendees);
    v_meeting_id := 'kairos-m-' || gen_random_uuid()::text;
    INSERT INTO public.meetings(
      id,client_id,title,date,summary,attendees,upcoming,product_id,
      organizer_employee_id,starts_at,ends_at,kairos_request_id,kairos_payload_hash
    ) VALUES (
      v_meeting_id,p_client_id,p_title,(p_start AT TIME ZONE 'Asia/Kolkata')::date,
      coalesce(nullif(btrim(p_purpose),''),'Scheduled through KAIROS'),v_names,TRUE,NULL,
      v_organizer,p_start,p_end,p_request_id,v_fingerprint
    );
    FOREACH v_employee IN ARRAY v_attendees LOOP
        INSERT INTO public.meeting_participants(meeting_id,participant_key,employee_id,external_name,role)
        VALUES (v_meeting_id,v_employee,v_employee,NULL,
                CASE WHEN v_employee=v_organizer THEN 'Organizer' ELSE 'Attendee' END);
        v_block_id := 'kairos-block-' || gen_random_uuid()::text;
        INSERT INTO public.employee_schedule_blocks(
            id,employee_id,project_id,starts_at,ends_at,block_type,description,meeting_id
        ) VALUES (
            v_block_id,v_employee,p_project_id,p_start,p_end,'Meeting',
            'Meeting — '||p_title,v_meeting_id
        );
        v_block_ids := array_append(v_block_ids,v_block_id);
    END LOOP;
    RETURN jsonb_build_object(
       'id',v_meeting_id,'title',p_title,'starts_at',p_start,'ends_at',p_end,
       'organizer_employee_id',v_organizer,'participant_employee_ids',v_attendees,
       'schedule_block_ids',v_block_ids,'replayed',FALSE);
END;
$fn$;

REVOKE ALL ON FUNCTION public.kairos_create_meeting_v1(
    text,text,text,text,timestamptz,timestamptz,text[],uuid
) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.kairos_create_meeting_v1(
    text,text,text,text,timestamptz,timestamptz,text[],uuid
) TO authenticated;
COMMIT;
