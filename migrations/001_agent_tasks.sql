-- AgentRemote V5.0 - Unified Task Tracking
-- Migration: 001_agent_tasks.sql
-- Run: psql or Supabase SQL Editor

-- ── agent_tasks: tracks ALL tasks from ALL entry points ──
CREATE TABLE IF NOT EXISTS agent_tasks (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source        text NOT NULL CHECK (source IN ('telegram', 'cowork', 'pwa', 'github_action', 'manual')),
  task          text NOT NULL,
  status        text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'processing', 'completed', 'failed', 'cancelled')),
  result        text,
  chat_id       text,
  metadata      jsonb DEFAULT '{}'::jsonb,
  created_at    timestamptz NOT NULL DEFAULT now(),
  completed_at  timestamptz
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_agent_tasks_status ON agent_tasks(status);
CREATE INDEX IF NOT EXISTS idx_agent_tasks_source ON agent_tasks(source);
CREATE INDEX IF NOT EXISTS idx_agent_tasks_created ON agent_tasks(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_tasks_chat_id ON agent_tasks(chat_id) WHERE chat_id IS NOT NULL;

-- RLS: service role only (executor writes, no public access)
ALTER TABLE agent_tasks ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_full_access" ON agent_tasks
  FOR ALL
  USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

-- View for quick Telegram history queries
CREATE OR REPLACE VIEW agent_tasks_recent AS
SELECT 
  id,
  source,
  LEFT(task, 100) AS task_preview,
  status,
  LEFT(result, 200) AS result_preview,
  metadata->>'duration_ms' AS duration_ms,
  metadata->>'command' AS command,
  created_at,
  completed_at,
  EXTRACT(EPOCH FROM (completed_at - created_at))::int AS elapsed_seconds
FROM agent_tasks
ORDER BY created_at DESC
LIMIT 50;

-- Daily stats view
CREATE OR REPLACE VIEW agent_tasks_daily_stats AS
SELECT 
  date_trunc('day', created_at)::date AS day,
  source,
  COUNT(*) AS total,
  COUNT(*) FILTER (WHERE status = 'completed') AS completed,
  COUNT(*) FILTER (WHERE status = 'failed') AS failed,
  AVG((metadata->>'duration_ms')::numeric) FILTER (WHERE metadata->>'duration_ms' IS NOT NULL) AS avg_duration_ms
FROM agent_tasks
GROUP BY 1, 2
ORDER BY 1 DESC, 2;

COMMENT ON TABLE agent_tasks IS 'AgentRemote V5 unified task log - all entry points (Telegram, Co-work, PWA, GHA)';
