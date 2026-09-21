# modeling-pipeline

Stack local de [MLflow](https://mlflow.org/) para experimentación, levantado con
Docker Compose:

| Servicio | Rol | Imagen |
| --- | --- | --- |
| `tracking_server` | Servidor de MLflow (UI + API) | build local desde `mlflow/Dockerfile` |
| `db` | Backend store: experimentos, runs, params y métricas | `postgres:16` |
| `s3` | Artifact store: artefactos y modelos | `quay.io/minio/minio` |
| `create_buckets` | Job de un solo uso que crea el bucket `mlflow` | `quay.io/minio/mc` |

El tracking server corre con `--serve-artifacts`, así que el cliente nunca habla
directo con MinIO: todo pasa por el servidor.

## Requisitos

- Docker Desktop
- El entorno conda `mlops` (Python 3.11, con `mlflow`, `scikit-learn` y `pandas`)
  para correr hello mlflow:

  ```bash
  conda activate mlops
  ```

  El cliente de MLflow vive ahí, no en `base`. Si lo corres desde `base` vas a
  ver `ModuleNotFoundError: No module named 'mlflow'`.

## Cómo levantarlo

### 1. Configura las variables

```bash
cp config.env.example config.env
```

Cambia `PG_PASSWORD` y `MINIO_ROOT_PASSWORD` **antes** de levantar el stack por
primera vez: Postgres graba su password al inicializar `db_data/` y después
editar el archivo ya no la cambia (ver la nota al final).

Las access keys de MinIO se llenan hasta el paso 3, déjalas vacías por ahora.

### 2. Levanta el stack

```bash
docker compose --env-file config.env up -d --build
```

Si prefieres no escribir `--env-file` cada vez, crea un enlace para que Compose
lo tome solo:

```bash
ln -s config.env .env
docker compose up -d --build
```

Verifica que los tres servicios estén `healthy`:

```bash
docker compose ps
```

### 3. Genera las access keys

**Opción A — consola web.** Entra a **http://localhost:9001** con el
`MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` de tu `config.env`, y crea una access
key en *Access Keys → Create access key*.

**Opción B — línea de comandos**, sustituyendo usuario y password por los tuyos:

```bash
docker compose --env-file config.env run --rm --no-deps \
  -e MC_HOST_s3=http://minio_user:tu_password@s3:9000 \
  --entrypoint mc create_buckets \
  admin accesskey create s3/ --name mlflow
```

Ojo con el puerto: `mc admin` habla por la **API (9000)**, no por la consola
(9001). Con 9001 falla con `Unable to add service account. S3 API Requests must
be made to API port`.

Copia el par a `config.env`:

```
MINIO_ACCESS_KEY=...
MINIO_SECRET_ACCESS_KEY=...
```

Y recrea los servicios para que tomen las credenciales:

```bash
docker compose --env-file config.env up -d --force-recreate tracking_server create_buckets
```

Aquí van los nombres de **servicio** del compose, no los de contenedor: el
servidor es `tracking_server` (`mlflow_server` es el `container_name`). Con el
nombre equivocado Compose responde `no such service`.

`create_buckets` debe terminar con `Bucket created successfully s3/mlflow`:

```bash
docker logs mlflow_create_buckets
```

### 4. Corre hello mlflow

```bash
conda activate mlops
python hello_mlflow.py
```

Entrena una regresión logística sobre Iris y registra params, métricas, un
reporte de clasificación y el modelo con su firma. Deberías ver algo así:

```
accuracy = 0.9667
f1_macro = 0.9666
🏃 View run regresion-logistica-iris at: http://localhost:5001/#/experiments/1/runs/...
```

## Interfaces

| Qué | URL |
| --- | --- |
| MLflow | http://localhost:5001 |
| Consola de MinIO | http://localhost:9001 |
| API de MinIO | http://localhost:9000 |

Los runs no se ven en la pantalla inicial de *Experiments*: esa tabla lista
experimentos. Hay que entrar a `hello-mlflow` para ver las corridas.

## Detalles que cuestan un rato descubrir

**El puerto de MLflow es 5001, no 5000.** En macOS el receptor AirPlay ocupa el
5000 y responde `403` con cuerpo vacío, lo que parece un error de MLflow pero no
lo es. Se puede liberar en *Ajustes del Sistema → General → AirDrop y Handoff*,
pero es más simple usar otro puerto.

**Las imágenes de MinIO salen de quay.io.** Docker Hub ya no permite pulls
anónimos de la organización `minio/*`; falla con `pull access denied`.
`quay.io/minio/*` es el registro propio de MinIO y no pide login.

**Postgres está fijado a 16.** La imagen 18 cambió la ubicación de los datos y
rechaza el bind mount en `/var/lib/postgresql/data`, entrando en bucle de
reinicio.

**Descargar artefactos desde el host necesita una variable extra.** MLflow pide
URLs prefirmadas que apuntan a `http://s3:9000`, un nombre que solo resuelve
dentro de la red de Docker. Sin esto, `load_model` y `download_artifacts` se
quedan reintentando en silencio:

```python
os.environ.setdefault("MLFLOW_ENABLE_PROXY_MULTIPART_DOWNLOAD", "false")
```

Va antes de importar `mlflow`, como en `hello_mlflow.py`.

**La password de Postgres solo se aplica al crear el volumen.** `POSTGRES_PASSWORD`
se usa la primera vez que se inicializa `db_data/`; después, cambiar
`PG_PASSWORD` en `config.env` no cambia nada en la base y el servidor queda en
bucle con `FATAL: password authentication failed for user "mlflow"`. Se
sincroniza sin borrar datos:

```bash
docker exec mlflow_db psql -U mlflow -d mlflow \
  -c "ALTER USER mlflow WITH PASSWORD 'la_de_config_env';"
docker compose --env-file config.env restart tracking_server
```

**MinIO necesita espacio libre en disco.** Por debajo de su umbral mínimo
rechaza las escrituras con `XMinioStorageFull` y las subidas de artefactos
fallan. `docker builder prune` suele liberar bastante.

## Datos y limpieza

Los datos viven en el repositorio pero están fuera de git: `db_data/` (Postgres)
y `minio_data/` (MinIO). Para apagar el stack conservándolos:

```bash
docker compose down
```

Para empezar de cero, bórralos después de apagar el stack.
