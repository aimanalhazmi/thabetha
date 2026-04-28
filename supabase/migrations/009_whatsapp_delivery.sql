-- 009_whatsapp_delivery.sql
-- Phase 6: Real WhatsApp Business API integration (006-whatsapp-business-integration)
-- Adds delivery-state columns to notifications. Existing RLS unchanged.

ALTER TABLE notifications
    ADD COLUMN IF NOT EXISTS whatsapp_attempted boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS whatsapp_delivered boolean,
    ADD COLUMN IF NOT EXISTS whatsapp_provider_ref text,
    ADD COLUMN IF NOT EXISTS whatsapp_failed_reason text,
    ADD COLUMN IF NOT EXISTS whatsapp_status_received_at timestamptz;

CREATE UNIQUE INDEX IF NOT EXISTS notifications_whatsapp_provider_ref_key
    ON notifications (whatsapp_provider_ref)
    WHERE whatsapp_provider_ref IS NOT NULL;

CREATE INDEX IF NOT EXISTS notifications_whatsapp_provider_ref_idx
    ON notifications (whatsapp_provider_ref);
