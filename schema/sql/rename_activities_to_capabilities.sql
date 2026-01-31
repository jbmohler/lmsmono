-- Migration: Rename activities to capabilities
-- Run this manually against the database before deploying the new code

-- Rename activities table to capabilities
ALTER TABLE activities RENAME TO capabilities;
ALTER TABLE capabilities RENAME COLUMN act_name TO cap_name;

-- Rename roleactivities to rolecapabilities
ALTER TABLE roleactivities RENAME TO rolecapabilities;
ALTER TABLE rolecapabilities RENAME COLUMN activityid TO capabilityid;
