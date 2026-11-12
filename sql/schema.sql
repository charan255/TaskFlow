CREATE DATABASE IF NOT EXISTS taskflow
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE taskflow;

CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT UNSIGNED NOT NULL,
    username VARCHAR(255) NULL,
    first_name VARCHAR(255) NOT NULL,
    registered_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS tasks (
    task_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id BIGINT UNSIGNED NOT NULL,
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    priority ENUM('low', 'medium', 'high') NOT NULL DEFAULT 'medium',
    due_date DATE NULL,
    status ENUM('pending', 'completed') NOT NULL DEFAULT 'pending',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    completed_at DATETIME NULL,
    PRIMARY KEY (task_id),
    CONSTRAINT fk_tasks_user
        FOREIGN KEY (user_id) REFERENCES users (user_id)
        ON DELETE RESTRICT,
    CONSTRAINT chk_tasks_completion_timestamp
        CHECK (
            (status = 'pending' AND completed_at IS NULL)
            OR (status = 'completed' AND completed_at IS NOT NULL)
        ),
    INDEX idx_tasks_user_status_due (user_id, status, due_date),
    INDEX idx_tasks_user_priority_status (user_id, priority, status)
) ENGINE=InnoDB;
