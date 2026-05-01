# testcontainers-python — Module Reference

All modules are installed via `pip install testcontainers[<extra>]`.

## Databases

| Module | Extra | Import | Container Class |
|---|---|---|---|
| PostgreSQL | `postgres` | `from testcontainers.postgres import PostgresContainer` | `PostgresContainer(image, username, password, dbname, driver)` |
| MySQL | `mysql` | `from testcontainers.mysql import MySqlContainer` | `MySqlContainer(image, username, password, dbname)` |
| MariaDB | `mysql` | `from testcontainers.mariadb import MariaDbContainer` | `MariaDbContainer(image, username, password, dbname)` |
| MongoDB | `mongodb` | `from testcontainers.mongodb import MongoDbContainer` | `MongoDbContainer(image)` |
| CockroachDB | `cockroachdb` | `from testcontainers.cockroachdb import CockroachDBContainer` | `CockroachDBContainer(image)` |
| Oracle | `oracle` | `from testcontainers.oracle import OracleDbContainer` | `OracleDbContainer(image)` |
| ClickHouse | `clickhouse` | `from testcontainers.clickhouse import ClickHouseContainer` | `ClickHouseContainer(image)` |

## Cache / Messaging

| Module | Extra | Import | Container Class |
|---|---|---|---|
| Redis | `redis` | `from testcontainers.redis import RedisContainer` | `RedisContainer(image)` |
| Kafka | `kafka` | `from testcontainers.kafka import KafkaContainer` | `KafkaContainer(image)` → `.get_bootstrap_server()` |
| RabbitMQ | `rabbitmq` | `from testcontainers.rabbitmq import RabbitMqContainer` | `RabbitMqContainer(image)` |
| Apache Pulsar | `pulsar` | `from testcontainers.pulsar import PulsarContainer` | `PulsarContainer(image)` |

## Search / Vector Stores

| Module | Extra | Import | Container Class |
|---|---|---|---|
| Elasticsearch | `elasticsearch` | `from testcontainers.elasticsearch import ElasticsearchContainer` | `ElasticsearchContainer(image)` → `.get_url()` |
| OpenSearch | `opensearch` | `from testcontainers.opensearch import OpenSearchContainer` | `OpenSearchContainer(image)` |
| Weaviate | `weaviate` | `from testcontainers.weaviate import WeaviateContainer` | `WeaviateContainer(image)` |
| Qdrant | `qdrant` | `from testcontainers.qdrant import QdrantContainer` | `QdrantContainer(image)` |
| Chroma | `chroma` | `from testcontainers.chroma import ChromaContainer` | `ChromaContainer(image)` |

## Cloud Emulators

| Module | Extra | Import | Container Class |
|---|---|---|---|
| LocalStack | `localstack` | `from testcontainers.localstack import LocalStackContainer` | `LocalStackContainer(image)` → `.get_url()` |
| MinIO | `minio` | `from testcontainers.minio import MinioContainer` | `MinioContainer(image)` → `.get_client()` |
| Azurite | `azurite` | `from testcontainers.azurite import AzuriteContainer` | `AzuriteContainer(image)` |

## Generic / Custom

| Module | Extra | Import | Container Class |
|---|---|---|---|
| Generic container | `generic` | `from testcontainers.core.container import DockerContainer` | `DockerContainer(image)` |
| Server container | `generic` | `from testcontainers.generic import ServerContainer` | `ServerContainer(port, startup_check_fn)` |

## Useful Core Utilities

```python
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_strategy import wait_for_logs
from testcontainers.core.config import testcontainers_config

# DockerContainer methods:
.with_exposed_ports(port)        # expose an internal port (mapped randomly on host)
.with_env(key, value)            # set environment variable
.with_volume_mapping(host, container, mode="ro")  # mount a volume
.with_command(cmd)               # override entrypoint command
.with_kwargs(**docker_kwargs)    # pass raw kwargs to docker-py
.get_container_host_ip()         # returns host IP reachable from test
.get_exposed_port(internal_port) # returns mapped host port as string
.get_logs()                      # returns (stdout, stderr) bytes tuple

# Config:
testcontainers_config.ryuk_disabled = True
testcontainers_config.ryuk_docker_socket = "/var/run/docker.sock"
```

## Connection URL Helpers

Most database containers expose a `get_connection_url()` method returning a SQLAlchemy-compatible URL:

```
postgresql+psycopg2://user:pass@localhost:PORT/dbname
mysql+pymysql://user:pass@localhost:PORT/dbname
```

For non-SQL containers, use `get_container_host_ip()` + `get_exposed_port(N)` to build the URL manually.
