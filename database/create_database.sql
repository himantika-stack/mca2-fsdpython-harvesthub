-- Run once as a MySQL administrator. Replace the quoted password before execution.
CREATE DATABASE IF NOT EXISTS harvesthub CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'harvesthub_user'@'localhost' IDENTIFIED BY 'replace_with_a_strong_password';
GRANT ALL PRIVILEGES ON harvesthub.* TO 'harvesthub_user'@'localhost';
FLUSH PRIVILEGES;
