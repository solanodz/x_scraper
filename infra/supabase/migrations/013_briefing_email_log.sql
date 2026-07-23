-- infra/supabase/migrations/013_briefing_email_log.sql
-- Idempotency log for Morning Briefing Email (F46).
-- Unique per Operator + calendar day (sent_on in BRIEFING_EMAIL_TZ).

CREATE TABLE IF NOT EXISTS briefing_email_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  operator_id UUID NOT NULL,
  sent_on DATE NOT NULL,
  resend_id TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (operator_id, sent_on)
);
