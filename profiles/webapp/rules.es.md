#### Perfil aplicación web
- Antes de cambiar el esquema de base de datos revisa migraciones existentes y su estado en producción (registro de despliegues); las migraciones destructivas requieren aprobación.
- Secretos solo por variables de entorno/gestor de secretos; ejecuta pruebas y linters del proyecto antes de dar una tarea por terminada.
- Tras desplegar y verificar salud, registra el commit (`memory_deploy.py record`); toda subida de dependencia por seguridad cita el CVE en el commit.
