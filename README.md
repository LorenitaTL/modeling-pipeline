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
- Python 3.11 con `mlflow`, `scikit-learn` y `pandas` para correr el smoke test

## Cómo levantarlo

### 1. Configura las variables

```bash
cp config.env.example config.env
```

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

Entra a la consola de MinIO en **http://localhost:9001** con el
`MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` de tu `config.env`, y crea una access
key en *Access Keys → Create access key*.

Copia el par a `config.env`:

```
MINIO_ACCESS_KEY=...
MINIO_SECRET_ACCESS_KEY=...
```

Y recrea los servicios para que tomen las credenciales:

```bash
docker compose up -d
```

`create_buckets` debe terminar con `Bucket created successfully s3/mlflow`:

```bash
docker logs mlflow_create_buckets
```

### 4. Corre el smoke test

```bash
python smoke_test.py
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
experimentos. Hay que entrar a `smoke-test` para ver las corridas.

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

Va antes de importar `mlflow`, como en `smoke_test.py`.

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
