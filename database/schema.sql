-- ============================================================================
-- SISTEMA DE ACREDITACIÓN Y CHECK-IN DACER
-- Script de Creación y Estructura de Base de Datos MySQL
-- Motor: InnoDB | Codificación: UTF8MB4 | Collation: utf8mb4_unicode_ci
-- ============================================================================

CREATE DATABASE IF NOT EXISTS `checkin_dacer_db`
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE `checkin_dacer_db`;

-- Desactivar temporalmente revisión de claves foráneas para orden de creación limpio
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------------------------------------------------------
-- 1. TABLA: events (Gestión Multi-Evento)
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS `events`;
CREATE TABLE `events` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `slug` VARCHAR(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` VARCHAR(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` TEXT COLLATE utf8mb4_unicode_ci,
  `location` VARCHAR(150) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `start_date` DATETIME DEFAULT NULL,
  `end_date` DATETIME DEFAULT NULL,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `onedrive_url` TEXT COLLATE utf8mb4_unicode_ci,
  `label_template` TEXT COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `cache_filename` VARCHAR(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `last_sync` DATETIME DEFAULT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_events_slug` (`slug`),
  KEY `ix_events_is_active` (`is_active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 2. TABLA: users (Usuarios del Sistema, Autenticación y RBAC)
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS `users`;
CREATE TABLE `users` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `username` VARCHAR(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `email` VARCHAR(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `password_hash` VARCHAR(256) COLLATE utf8mb4_unicode_ci NOT NULL,
  `role` VARCHAR(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'OPERADOR', -- ADMIN, SUPERVISOR, OPERADOR
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `must_change_password` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `last_login` DATETIME DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_users_username` (`username`),
  UNIQUE KEY `email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 3. TABLA: guests (Participantes e Invitados por Evento)
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS `guests`;
CREATE TABLE `guests` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `event_id` INT NOT NULL,
  `guest_code` VARCHAR(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `full_name` VARCHAR(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  `company` VARCHAR(150) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `position` VARCHAR(150) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `email` VARCHAR(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `phone` VARCHAR(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `category` VARCHAR(50) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'GENERAL',
  `qr_hash` VARCHAR(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_event_guest_code` (`event_id`, `guest_code`),
  KEY `ix_guests_event_id` (`event_id`),
  KEY `ix_guests_full_name` (`full_name`),
  KEY `ix_guests_guest_code` (`guest_code`),
  KEY `ix_guests_qr_hash` (`qr_hash`),
  CONSTRAINT `fk_guests_events` FOREIGN KEY (`event_id`) REFERENCES `events` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 4. TABLA: face_profiles (Vectores Biométricos SFace y Miniaturas en Memoria)
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS `face_profiles`;
CREATE TABLE `face_profiles` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `guest_id` INT NOT NULL,
  `image_id` VARCHAR(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `filename` VARCHAR(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `thumb_filename` VARCHAR(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `thumb_data` MEDIUMTEXT COLLATE utf8mb4_unicode_ci, -- Almacenamiento base64 en MySQL (cero archivos en disco)
  `embedding_json` TEXT COLLATE utf8mb4_unicode_ci NOT NULL, -- Vector normalizado L2 de 128 dimensiones
  `quality_score` FLOAT DEFAULT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_face_profiles_guest_id` (`guest_id`),
  KEY `ix_face_profiles_image_id` (`image_id`),
  CONSTRAINT `fk_face_profiles_guests` FOREIGN KEY (`guest_id`) REFERENCES `guests` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 5. TABLA: checkins (Registros de Asistencia Físicos Confirmados)
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS `checkins`;
CREATE TABLE `checkins` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `event_id` INT NOT NULL,
  `guest_id` INT NOT NULL,
  `verified_by_user_id` INT DEFAULT NULL,
  `method` VARCHAR(20) COLLATE utf8mb4_unicode_ci NOT NULL, -- QR, FACIAL, MANUAL
  `confidence_score` FLOAT DEFAULT NULL,
  `kiosk_identifier` VARCHAR(64) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'KIOSK-MAIN',
  `ip_address` VARCHAR(45) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `printed_success` TINYINT(1) NOT NULL DEFAULT 1,
  `checked_in_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_checkins_event_id` (`event_id`),
  KEY `ix_checkins_guest_id` (`guest_id`),
  KEY `ix_checkins_checked_in_at` (`checked_in_at`),
  KEY `fk_checkins_users` (`verified_by_user_id`),
  CONSTRAINT `fk_checkins_events` FOREIGN KEY (`event_id`) REFERENCES `events` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_checkins_guests` FOREIGN KEY (`guest_id`) REFERENCES `guests` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_checkins_users` FOREIGN KEY (`verified_by_user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 6. TABLA: audit_logs (Pistas de Auditoría y Trazabilidad Operativa)
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS `audit_logs`;
CREATE TABLE `audit_logs` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT DEFAULT NULL,
  `action` VARCHAR(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `target_type` VARCHAR(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `target_id` VARCHAR(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `details` TEXT COLLATE utf8mb4_unicode_ci,
  `ip_address` VARCHAR(45) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_audit_logs_action` (`action`),
  KEY `ix_audit_logs_created_at` (`created_at`),
  KEY `fk_audit_logs_users` (`user_id`),
  CONSTRAINT `fk_audit_logs_users` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 7. TABLA: kiosk_settings (Configuración Operativa por Evento)
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS `kiosk_settings`;
CREATE TABLE `kiosk_settings` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `event_id` INT DEFAULT NULL,
  `scan_method` VARCHAR(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'both', -- both, facial, qr
  `operation_mode` VARCHAR(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'manual', -- manual, auto
  `face_threshold` FLOAT NOT NULL DEFAULT 0.70,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_kiosk_event_id` (`event_id`),
  CONSTRAINT `fk_kiosk_settings_events` FOREIGN KEY (`event_id`) REFERENCES `events` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Reactivar revisión de claves foráneas
SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================================
-- DATOS SEMILLA INICIALES (Bootstrap)
-- ============================================================================

-- Evento Principal por Defecto
INSERT INTO `events` (`id`, `slug`, `name`, `description`, `location`, `is_active`, `created_at`)
VALUES (1, 'evento-demo-2026', 'EVENTO DEMO 2026', 'Evento principal de demostración y acreditación', 'Lima, Perú', 1, NOW())
ON DUPLICATE KEY UPDATE `name` = VALUES(`name`);

-- Configuración del Kiosko para el Evento 1
INSERT INTO `kiosk_settings` (`event_id`, `scan_method`, `operation_mode`, `face_threshold`, `updated_at`)
VALUES (1, 'both', 'manual', 0.70, NOW())
ON DUPLICATE KEY UPDATE `face_threshold` = VALUES(`face_threshold`);

-- Usuario Administrador por Defecto
-- Username: Admin
-- Password inicial: 000000 (Hash generado con scrypt werkzeug)
-- must_change_password: 1 (Obliga a cambiar contraseña al primer login)
INSERT INTO `users` (`username`, `email`, `password_hash`, `role`, `is_active`, `must_change_password`, `created_at`)
VALUES ('Admin', 'admin@dacer.com.pe', 'scrypt:32768:8:1$7pL0T1u31B9tqWzJ$97bb0c0c29f6b405527be636a0d2f093a558509c122137024f9fa5182cfc3a1e3895e6f3b060d4b8e8ea6f423ab55b39922e43f25c79eecb77b7f1e63d3c8c69', 'ADMIN', 1, 1, NOW())
ON DUPLICATE KEY UPDATE `role` = 'ADMIN';

-- Registro de Auditoría Inicial
INSERT INTO `audit_logs` (`action`, `target_type`, `target_id`, `details`, `created_at`)
VALUES ('SCHEMA_INIT', 'DATABASE', 'checkin_dacer_db', 'Base de datos y tablas inicializadas con éxito.', NOW());
