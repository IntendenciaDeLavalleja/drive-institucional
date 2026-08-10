# Despliegue en Coolify

## 1. Recursos

Crear una aplicación desde repositorio o Dockerfile y conectarla a:

- la MariaDB institucional (se recomienda una base y usuario exclusivos);
- Redis (puede reutilizarse con un número de base dedicado);
- MinIO existente mediante su hostname interno y puerto API 9000.

El servicio escucha en `PORT` (por defecto `5000`). Configurar el dominio, por ejemplo `drive.lavalleja.uy`, con HTTPS y usar `/health` como healthcheck de Coolify.

## 2. Variables

Copiar las claves de `.env.example` al panel de variables de Coolify. No subir un `.env` real al repositorio.

Puntos importantes:

- `MINIO_ENDPOINT` no lleva `http://` ni ruta.
- `MINIO_SECURE=false` suele corresponder al tráfico interno de Docker; usar `true` si el endpoint interno tiene TLS.
- `MINIO_BUCKET=lavalleja-drive` concede un espacio lógico propio a la aplicación.
- `FLASK_RUN_HOST` debe ser el dominio HTTPS público final y se usa para generar enlaces compartidos. `PUBLIC_BASE_URL` sólo se usa como fallback compatible.
- `DATABASE_URL` debe usar `mariadb+mariadbconnector://`.
- `REDIS_URL` debe contener contraseña si el Redis la exige.
- generar `SECRET_KEY` y `WTF_CSRF_SECRET_KEY` diferentes con un generador criptográfico.
- definir `PORT=5000`, salvo que Coolify asigne otro puerto interno.

## 3. Permisos de MinIO

Crear un usuario de servicio exclusivo. La política mínima sobre el bucket es:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": ["s3:CreateBucket", "s3:ListBucket", "s3:GetBucketLocation"],
    "Resource": ["arn:aws:s3:::lavalleja-drive"]
  }, {
    "Effect": "Allow",
    "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:AbortMultipartUpload", "s3:ListMultipartUploadParts"],
    "Resource": ["arn:aws:s3:::lavalleja-drive/*"]
  }]
}
```

No aplicar lectura pública al bucket. La aplicación crea el bucket al iniciar si aún no existe; la política debe incluir `s3:CreateBucket` o el bucket debe crearse previamente con un administrador.

## 4. Primera puesta en marcha

El `entrypoint.sh` ejecuta `flask db upgrade` antes de Gunicorn. Si la migración falla, el contenedor no inicia, evitando servir una versión incompatible. Una vez saludable el despliegue, abrir la terminal del contenedor:

```bash
flask create-admin nebyx usuario@lavalleja.uy "Contraseña-segura-123" true
```

El último argumento es `true` para superadmin o `false` para admin.
Un admin requiere como quinto argumento el nombre exacto de una unidad ya creada.

## 5. Retención de archivos

Los archivos se eliminan automáticamente de MinIO y de la aplicación a los 15 días de cargados. El contenedor ejecuta `flask prune-expired-files` al iniciar y cada 24 horas. Para una ejecución manual o una tarea programada de Coolify:

```bash
flask prune-expired-files
```

No configurar más de una réplica de la aplicación sin mantener MariaDB disponible: el comando usa un bloqueo de base de datos para que sólo una instancia procese vencimientos.

## 6. Archivos grandes

La aplicación acepta hasta 5 GiB por defecto (`MAX_UPLOAD_BYTES`). Gunicorn tiene un timeout de 900 segundos. Si se usa un proxy adicional, verificar:

- que no imponga un límite de cuerpo menor;
- que el timeout de lectura/escritura alcance para la conexión más lenta prevista;
- que no almacene el cuerpo completo en memoria.

El servidor web de Flask usa el archivo temporal administrado por Werkzeug y MinIO realiza multipart de 64 MiB; no carga el archivo completo en RAM. Para cargas de varios gigabytes conviene reservar espacio temporal suficiente en el host.

Cloudflare y otros proxies pueden imponer límites por plan; para archivos mayores se recomienda que el subdominio no atraviese un proxy con límite inferior.

## 7. Backups

Respaldar juntos:

- la base MariaDB;
- el bucket `lavalleja-drive`;
- las variables/secretos de la aplicación.

La base sin el bucket conserva auditoría y nombres, pero no el contenido. El bucket sin la base no conserva carpetas, propietarios ni enlaces.

## 8. Verificación

1. `/health` responde `{"status":"ok"}` y verifica MariaDB y MinIO.
2. El correo 2FA llega y el código solo funciona una vez.
3. Se puede subir y descargar un archivo de prueba.
4. Un enlace con contraseña funciona y luego puede revocarse.
5. Los eventos aparecen en Auditoría para el superadministrador.
6. El panel Vencimientos muestra los archivos activos y `flask prune-expired-files` elimina los que superaron 15 días.
