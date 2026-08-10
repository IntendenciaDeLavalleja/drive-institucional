# Drive Institucional de Lavalleja

Gestor institucional de archivos preparado para Coolify, Flask, MariaDB, Redis y un MinIO existente. Permite organizar documentos en carpetas y compartir archivos grandes mediante enlaces revocables, sin publicar el bucket.

## Funciones incluidas

- Inicio de sesión con contraseña Argon2 y segundo factor por correo.
- Roles `admin` y `superadmin`.
- Carpetas jerárquicas: crear, abrir, renombrar y eliminar recursivamente.
- Carga múltiple con barra de progreso y streaming multipart hacia MinIO.
- Nombre visible independiente de la clave física del objeto.
- Descarga interna y externa con soporte HTTP Range.
- Enlaces de archivo con vencimiento, contraseña, máximo de descargas y revocación.
- SHA-256, tamaño, tipo MIME, usuario y fechas de cada archivo.
- Auditoría administrativa y registro separado de accesos públicos.
- Bucket MinIO privado: la aplicación media todas las descargas.
- Migraciones automáticas, healthcheck, límites de tasa y cabeceras de seguridad.

## Inicio rápido local

1. Copiar `.env.example` a `.env` y adaptar los valores locales.
2. Ejecutar `docker compose -f docker-compose.local.yml up --build -d`.
3. Crear el primer usuario:

   ```bash
   docker compose -f docker-compose.local.yml exec app \
     flask create-admin administrador admin@lavalleja.uy "Contraseña-segura-123" true
   ```

4. Abrir `http://localhost:5000`.

Para despliegue institucional, seguir [docs/COOLIFY.md](docs/COOLIFY.md).

## Arquitectura

- Los metadatos viven en MariaDB.
- El contenido binario vive exclusivamente en el bucket configurado de MinIO.
- Redis almacena límites de tasa compartidos entre workers.
- El token público se guarda únicamente como SHA-256. El enlace completo solo se muestra al crearlo.
- Las contraseñas de usuarios, enlaces y códigos 2FA usan Argon2.
- El login requiere CAPTCHA matemático y un código 2FA enviado por correo.
- `wsgi.py`, `Dockerfile` y `entrypoint.sh` están preparados para Gunicorn/Coolify.
- Los admins comunes requieren una unidad asignada; los superadmins administran unidades, usuarios y auditoría.

## Pruebas

```bash
sudo apt-get install libmariadb-dev pkg-config
python -m pip install -r requirements-dev.txt
pytest -q
```
