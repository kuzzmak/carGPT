# CarGPT Backend - Docker Setup

Complete Docker Compose setup for the CarGPT backend with PostgreSQL database, FastAPI application, and optional PgAdmin interface.

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose installed
- `uv` package manager (for local development)

### 1. Environment Setup
```bash
# Copy environment template
cp .env.example .env

# Edit configuration if needed
nano .env
```

### 2. Start Services
```bash
# Using Make (recommended)
make up

# Or using Docker Compose directly
docker-compose up -d
```

### 3. Access Services
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Database**: localhost:5432
- **PgAdmin** (optional): http://localhost:5050

## 🛠️ Available Commands

### Using Make (Recommended)
```bash
make help           # Show all available commands
make up             # Start all services
make down           # Stop all services
make logs           # Show logs from all services
make shell          # Open shell in backend container
make test           # Run API tests
make rebuild        # Rebuild and restart services
```

### Direct Docker Compose Commands
```bash
# Development
docker-compose up -d                    # Start services
docker-compose down                     # Stop services
docker-compose logs -f                  # Show logs
docker-compose ps                       # Show status

# With tools (PgAdmin)
docker-compose --profile tools up -d    # Start with PgAdmin
docker-compose --profile tools down     # Stop with PgAdmin

# Production
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## 📁 Project Structure

```
carGPT/backend/
├── docker-compose.yml      # Main Docker Compose configuration
├── docker-compose.prod.yml # Production overrides
├── Dockerfile              # Backend container definition
├── init.sql               # Database initialization script
├── Makefile               # Convenient command shortcuts
├── .env.example           # Environment configuration template
├── .dockerignore          # Docker build ignore patterns
├── main.py                # FastAPI application
├── database.py            # Database connection class
├── test_api.py            # API test suite
└── start_server.sh        # Local development startup script
```

## 🔧 Configuration

### Environment Variables (.env file)
```bash
# Database Configuration
CARGPT_DB_NAME=ads_db
CARGPT_DB_USER=adsuser
CARGPT_DB_PASSWORD=pass
CARGPT_DB_HOST=localhost
CARGPT_DB_PORT=5432

# Application Configuration
UVICORN_RELOAD=true
UVICORN_WORKERS=1
LOG_LEVEL=info

# PgAdmin Configuration (optional)
PGLADMIN_DEFAULT_EMAIL=admin@cargpt.com
PGLADMIN_DEFAULT_PASSWORD=admin123
```

### Service Configuration

#### PostgreSQL Database
- **Image**: `postgres:15-alpine`
- **Port**: 5432 (configurable via env)
- **Data**: Persisted in Docker volume
- **Initialization**: Automatic via `init.sql`

#### FastAPI Backend
- **Built from**: Local Dockerfile
- **Port**: 8000
- **Hot Reload**: Enabled in development
- **Health Check**: Available at `/health`

#### PgAdmin (Optional)
- **Image**: `dpage/pgadmin4:latest`
- **Port**: 5050
- **Profile**: `tools` (start with `--profile tools`)

## 🏗️ Development Workflow

### 1. Initial Setup
```bash
# Clone and navigate to backend directory
cd carGPT/backend

# Copy environment file
cp .env.example .env

# Start development environment
make dev-setup
```

### 2. Development Cycle
```bash
# Start services
make up

# View logs
make logs

# Test API
make test

# Make code changes (auto-reload enabled)
# Edit main.py, database.py, etc.

# Restart if needed
make restart

# Stop when done
make down
```

### 3. Database Management
```bash
# Open database shell
make shell-db

# Create backup
make db-backup

# Restore backup
make db-restore BACKUP_FILE=backups/ads_db_20240815_120000.sql

# Access PgAdmin interface
make up-tools
# Visit http://localhost:5050
```

## 🚀 Production Deployment

### 1. Production Configuration
```bash
# Update .env for production
CARGPT_DB_PASSWORD=secure_production_password
UVICORN_RELOAD=false
UVICORN_WORKERS=4
LOG_LEVEL=warning
```

### 2. Deploy
```bash
# Production deployment
make prod-deploy

# Or manually
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

### 3. Production Features
- **No hot reload** for better performance
- **Multiple workers** (4 by default)
- **Secure passwords** via environment variables
- **No volume mounting** (code baked into image)
- **Production logging** levels

## 🧪 Testing

### API Testing
```bash
# Test running containers
make test

# Manual testing
curl http://localhost:8000/health
curl http://localhost:8000/ads?limit=5
```

### Health Checks
All services include health checks:
- **Database**: PostgreSQL connection test
- **Backend**: HTTP health endpoint
- **Container Status**: `docker-compose ps`

## 🔍 Troubleshooting

### Common Issues

#### Port Conflicts
```bash
# Check what's using port 8000/5432
lsof -i :8000
lsof -i :5432

# Use different ports in .env
CARGPT_DB_PORT=5433
```

#### Database Connection Issues
```bash
# Check database logs
make logs-db

# Verify database is ready
docker-compose exec postgres pg_isready -U adsuser -d ads_db

# Reset database
make down-volumes  # ⚠️ Deletes data!
make up
```

#### Container Build Issues
```bash
# Clean rebuild
make clean
make rebuild

# Check container status
make status
docker-compose ps
```

### Logs and Debugging
```bash
# All services
make logs

# Specific service
make logs-backend
make logs-db

# Follow specific container
docker-compose logs -f backend
```

## 📚 API Documentation

Once running, comprehensive API documentation is available:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## 🔐 Security Considerations

### Development
- Default passwords (change for production)
- All interfaces exposed (okay for local development)
- Debug mode enabled

### Production
- Use strong passwords in environment variables
- Consider network restrictions
- Disable debug mode
- Use proper SSL termination (reverse proxy)

## 📦 Data Persistence

### Volumes
- `postgres_data`: Database files
- `pgladmin_data`: PgAdmin configuration

### Backups
```bash
# Create backup
make db-backup

# Backups stored in backups/ directory
ls -la backups/
```

## 🤝 Contributing

### Adding New Dependencies
```bash
# Update pyproject.toml
uv add new-package

# Rebuild container
make rebuild
```

### Database Schema Changes
```bash
# Update init.sql
# Then recreate database
make down-volumes
make up
```
