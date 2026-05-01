---
name: testcontainers-python
description: >
  Use this skill when the user wants to write integration tests or functional tests using Docker
  containers in Python with the testcontainers-python library. Trigger whenever the user mentions
  spinning up a database for tests, running Redis/Postgres/MySQL/Kafka/Elasticsearch/MongoDB in a
  test, testcontainers, Docker container in pytest, integration testing with real services, or wants
  to replace mocks with real containers. Also trigger when the user says things like "how do I test
  with a real database", "run a container in my test", "spin up services for testing", "pytest with
  Docker", or "integration test setup". Even if the user does not mention testcontainers by name,
  use this skill when the goal is using real containerised services in automated tests.
---

# testcontainers-python Skill

A skill for using [testcontainers-python](https://github.com/testcontainers/testcontainers-python) — a Python library that spins up Docker containers as real runtime environments for integration and functional tests.

## Core Concept

Testcontainers wraps Docker to give each test (or test session) a fresh, real service — no mocks, no external infra, no leftover state.

```python
# Typical pattern — context manager starts and stops the container
with PostgresContainer("postgres:16") as pg:
    engine = sqlalchemy.create_engine(pg.get_connection_url())
    # run your test code here
```

---

## Installation

```bash
# Install with the extras you need
pip install testcontainers[postgres]
pip install testcontainers[redis]
pip install testcontainers[kafka]
pip install testcontainers[mysql]
pip install testcontainers[mongodb]
pip install testcontainers[elasticsearch]
pip install testcontainers[minio]
pip install testcontainers[localstack]
pip install testcontainers[generic]   # for custom/arbitrary containers
```

Version 4.0+ uses extras — the old `testcontainers-postgres` style packages are no longer supported.

---

## Available Modules

See `references/modules.md` for the full module list with import paths and constructor signatures.

Key modules:
- **Databases**: PostgreSQL, MySQL, MariaDB, MongoDB, CockroachDB, ClickHouse, Oracle, DB2, Db2
- **Cache/Messaging**: Redis, Kafka, RabbitMQ, Pulsar, Azurite
- **Search**: Elasticsearch, OpenSearch, Weaviate, Qdrant, Chroma
- **Cloud emulators**: LocalStack (AWS), MinIO, Azurite
- **Generic / custom**: `DockerContainer`, `ServerContainer`, `GenericContainer`

---

## Core Patterns

### 1. Context Manager (simplest, per-test)

```python
from testcontainers.postgres import PostgresContainer
import sqlalchemy

def test_insert():
    with PostgresContainer("postgres:16") as pg:
        engine = sqlalchemy.create_engine(pg.get_connection_url())
        with engine.begin() as conn:
            conn.execute(sqlalchemy.text("CREATE TABLE t (id int)"))
            conn.execute(sqlalchemy.text("INSERT INTO t VALUES (1)"))
            result = conn.execute(sqlalchemy.text("SELECT * FROM t")).fetchall()
        assert result == [(1,)]
```

### 2. Pytest Fixture (session-scoped — start once, reuse)

```python
import pytest
from testcontainers.postgres import PostgresContainer

@pytest.fixture(scope="session")
def pg_container():
    with PostgresContainer("postgres:16") as pg:
        yield pg

def test_something(pg_container):
    url = pg_container.get_connection_url()
    # use url ...
```

Use `scope="session"` to avoid restarting the container for every test (much faster).  
Use `scope="function"` when you need full isolation per test.

### 3. Custom / Generic Container

```python
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_strategy import wait_for_logs

with DockerContainer("my-app:latest") \
        .with_exposed_ports(8080) \
        .with_env("ENV_VAR", "value") \
        .with_command("python -m myapp") as container:
    container.get_exposed_port(8080)  # mapped host port
```

### 4. Wait Strategies

Containers aren't immediately ready after `.start()`. Use waiting strategies:

```python
from testcontainers.core.waiting_strategy import (
    wait_for_logs,          # wait until log output matches a regex
    DockerReadinessProbe,   # custom callable
)

# Log-based (most common)
container = DockerContainer("redis:7").with_exposed_ports(6379)
container.with_kwargs(network="bridge")
# built-in modules handle this automatically

# For custom containers:
container = (
    DockerContainer("myimage:latest")
    .with_exposed_ports(8080)
)
container.start()
wait_for_logs(container, r"Application started", timeout=30)
```

Most built-in modules already implement their own readiness check — you don't need to configure waiting manually.

---

## Common Module Usage

### PostgreSQL

```python
from testcontainers.postgres import PostgresContainer

with PostgresContainer(
    image="postgres:16",
    username="testuser",
    password="testpass",
    dbname="testdb",
    driver="psycopg2",  # or None to exclude driver from URL
) as pg:
    url = pg.get_connection_url()  # postgresql+psycopg2://testuser:testpass@localhost:PORT/testdb
```

### MySQL / MariaDB

```python
from testcontainers.mysql import MySqlContainer
from testcontainers.mariadb import MariaDbContainer

with MySqlContainer("mysql:8.0") as mysql:
    url = mysql.get_connection_url()

with MariaDbContainer("mariadb:10.6") as mariadb:
    url = mariadb.get_connection_url()
```

### Redis

```python
from testcontainers.redis import RedisContainer
import redis

with RedisContainer("redis:7") as r:
    client = redis.Redis(
        host=r.get_container_host_ip(),
        port=r.get_exposed_port(6379),
    )
    client.set("key", "value")
    assert client.get("key") == b"value"
```

### MongoDB

```python
from testcontainers.mongodb import MongoDbContainer
from pymongo import MongoClient

with MongoDbContainer("mongo:6") as mongo:
    client = MongoClient(mongo.get_connection_url())
    db = client.testdb
```

### Kafka

```python
from testcontainers.kafka import KafkaContainer

with KafkaContainer("confluentinc/cp-kafka:7.4.0") as kafka:
    bootstrap_servers = kafka.get_bootstrap_server()
```

### Elasticsearch

```python
from testcontainers.elasticsearch import ElasticsearchContainer

with ElasticsearchContainer("elasticsearch:8.6.0") as es:
    url = es.get_url()  # http://localhost:PORT
```

### LocalStack (AWS)

```python
from testcontainers.localstack import LocalStackContainer
import boto3

with LocalStackContainer(image="localstack/localstack:3.0") as localstack:
    s3 = boto3.client(
        "s3",
        endpoint_url=localstack.get_url(),
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    s3.create_bucket(Bucket="my-bucket")
```

### MinIO

```python
from testcontainers.minio import MinioContainer
import boto3

with MinioContainer() as minio:
    client = minio.get_client()  # returns a Minio client
    # or get boto3-compatible endpoint:
    endpoint = f"http://{minio.get_container_host_ip()}:{minio.get_exposed_port(9000)}"
```

---

## Docker-in-Docker (CI)

When running inside a Docker container (e.g., GitHub Actions with DinD):

```yaml
# GitHub Actions example
services:
  docker:
    image: docker:dind
    options: --privileged

steps:
  - run: pip install testcontainers[postgres]
  - run: pytest
```

Environment variables to know:
| Variable | Purpose |
|---|---|
| `DOCKER_HOST` | Override Docker daemon socket |
| `TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE` | Path for Ryuk's socket |
| `TESTCONTAINERS_RYUK_DISABLED` | Set `true` to disable Ryuk (resource reaper) |
| `TESTCONTAINERS_HOST_OVERRIDE` | Override the IP Testcontainers uses to reach containers |
| `DOCKER_AUTH_CONFIG` | JSON auth for private registries |

---

## Custom Container from Scratch

```python
from testcontainers.core.container import DockerContainer

class MyServiceContainer(DockerContainer):
    def __init__(self, image="myrepo/myservice:latest", **kwargs):
        super().__init__(image=image, **kwargs)
        self.with_exposed_ports(8080)
        self.with_env("APP_ENV", "test")

    def get_url(self):
        host = self.get_container_host_ip()
        port = self.get_exposed_port(8080)
        return f"http://{host}:{port}"
```

---

## Tips & Gotchas

- **Ryuk** is the resource reaper — it automatically removes containers when the Python process exits. Disable with `TESTCONTAINERS_RYUK_DISABLED=true` only if it causes issues.
- **Port mapping**: containers expose ports dynamically. Always use `get_exposed_port(INTERNAL_PORT)` — never hardcode.
- **Image versions**: pin specific versions (e.g., `postgres:16`) to avoid flaky tests from upstream image changes.
- **Network access in CI**: if containers can't reach each other, consider `DockerContainer.with_kwargs(network="host")` or Docker Compose fixtures.
- **Slow startup**: use `scope="session"` fixtures and a single container per test session for expensive images.
- **`driver=None`** in `PostgresContainer`: useful with `psycopg` v3 which uses a different URL scheme.

---

## References

- Full module list: `references/modules.md`
- Official docs: https://testcontainers-python.readthedocs.io/en/latest/
- GitHub: https://github.com/testcontainers/testcontainers-python
