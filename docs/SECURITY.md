# Decisiones de seguridad

- El bucket nunca es público.
- Los tokens compartidos tienen 256 bits aleatorios y en la base solo queda su hash.
- Los enlaces pueden vencer, limitar descargas, requerir contraseña y revocarse.
- Usuarios, contraseñas de enlace y códigos 2FA se protegen con Argon2.
- Un código 2FA dura 10 minutos, tiene intentos limitados y se invalida al usarlo.
- Los formularios internos y públicos usan CSRF.
- Los intentos de login y accesos compartidos tienen rate limiting.
- Los nombres lógicos nunca se usan como claves de objeto, evitando traversal y colisiones.
- Se registra actor, fecha, IP, user-agent, acción, destino y detalle.
- Solo el superadministrador gestiona usuarios y consulta auditoría.
- El sistema evita desactivar o degradar al último superadministrador activo.

## Operación recomendada

- Usar cuentas individuales; no compartir credenciales.
- Revocar usuarios al cambiar de función.
- Dar al usuario de MinIO acceso únicamente al bucket de la aplicación.
- Rotar secretos y credenciales periódicamente.
- Conservar logs y backups según la política documental de la Intendencia.
- Analizar antivirus/antimalware en una fase posterior si se habilita carga desde equipos no gestionados.
