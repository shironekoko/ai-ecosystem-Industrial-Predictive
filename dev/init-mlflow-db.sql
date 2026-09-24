-- สร้าง database "mlflow" สำหรับ MLflow backend store
-- ไฟล์นี้จะถูก mount เข้า PostgreSQL container ผ่าน /docker-entrypoint-initdb.d/
-- PostgreSQL จะรันอัตโนมัติเมื่อ init ครั้งแรก

SELECT 'CREATE DATABASE mlflow'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'mlflow')\gexec
