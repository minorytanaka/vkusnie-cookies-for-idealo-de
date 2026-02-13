Поднять бд:
docker run --name vkusnie-postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=secretpassword \
  -e POSTGRES_DB=cookies \
  -d \
  -p 5432:5432 \
  -v ~/vkusnie_postgres_data:/var/lib/postgresql/data \
  postgres:latest

Запустить API:
cd api && sh start.sh

Запустить сборщик куков:
cd cookie_collector && sh start.sh
