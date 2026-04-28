# Docker Setup

> **TL;DR**: This project uses Docker for local development and production. All services are defined in `docker-compose.yaml`.

## Quick Start

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop all services
docker-compose down
```

## Services

| Service | Port | Purpose |
|---------|------|---------|
| **app** | 5000 | Flask application server |
| **db** | 5432 | PostgreSQL database |
| **redis** | 6379 | Caching layer |

## Development vs Production

### Development
```bash
docker-compose up
```
- Hot reload enabled
- Debug logging
- Exposed ports for debugging

### Production
```bash
docker-compose -f docker-compose.yaml up -d --build
```
- Optimized builds
- Minimal logging
- Health checks enabled

## Environment Variables

Create a `.env` file in the project root:

```bash
# Database
DATABASE_URL=postgresql://user:password@db:5432/mydb

# Redis
REDIS_URL=redis://redis:6379/0

# Flask
FLASK_ENV=development
SECRET_KEY=your-secret-key
```

## Common Commands

### Rebuild after dependency changes
```bash
docker-compose build --no-cache
```

### Run migrations
```bash
docker-compose exec app python -m flask db upgrade
```

### Access database directly
```bash
docker-compose exec db psql -U user -d mydb
```

### View container resource usage
```bash
docker stats
```

## Troubleshooting

### Container won't start
```bash
# Check logs
docker-compose logs app

# Rebuild
docker-compose up --build
```

### Database connection refused
```bash
# Wait for db to be ready
docker-compose up -d db
sleep 10
docker-compose up -d app
```

### Port already in use
```bash
# Find and kill process using port 5000
lsof -i :5000
```

## Best Practices for Agent Code

### ✅ DO
- Use environment variables for all configuration
- Add health check endpoints to new services
- Log with appropriate levels (DEBUG for dev, INFO for prod)
- Use docker-compose.override.yml for local dev

### ❌ DON'T
- Don't hardcode credentials in Dockerfiles
- Don't expose unnecessary ports
- Don't use :latest tags (use specific versions)
- Don't forget to add .dockerignore