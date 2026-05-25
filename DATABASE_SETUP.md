# 🗄️ Database Setup Guide (macOS)

This guide provides step-by-step instructions to get **PostgreSQL** and **Weaviate** running on your MacBook. These are required for Vella/Volco to store chat history and semantic memory.

---

## 1. PostgreSQL (Relational Data)
PostgreSQL stores users, sessions, and message logs.

### Installation via Homebrew
1. **Install PostgreSQL:**
   ```bash
   brew install postgresql@15
   ```
2. **Start the Service:**
   ```bash
   brew services start postgresql@15
   ```
3. **Create the 'vella' Database:**
   ```bash
   # Enter the postgres shell
   psql postgres
   
   # Inside the shell, run:
   CREATE DATABASE vella;
   \q
   ```
4. **Verify Connection:**
   Your `.env` file is already configured to look for:
   `DATABASE_URL="postgresql://postgres@localhost:5432/vella"`
   *(Note: On Mac, the default user is often your macOS username with no password. If you set a password, update the .env accordingly.)*

---

## 2. Weaviate (Vector Memory)
Weaviate handles long-term semantic memory. The easiest way to run it on Mac is via **Docker**.

### Prerequisites
- Install **Docker Desktop** for Mac: [Download Here](https://www.docker.com/products/docker-desktop/)

### Setup & Run
1. **Create a folder for Weaviate (Optional but recommended):**
   ```bash
   mkdir ~/weaviate-data
   cd ~/weaviate-data
   ```
2. **Create a `docker-compose.yml` file:**
   ```yaml
   version: '3.4'
   services:
     weaviate:
       command:
       - --host
       - 0.0.0.0
       - --port
       - '8080'
       - --scheme
       - http
       image: semitechnologies/weaviate:1.24.1
       ports:
       - 8080:8080
       restart: on-failure:0
       environment:
         QUERY_DEFAULTS_LIMIT: 25
         AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED: 'true'
         PERSISTENCE_DATA_PATH: '/var/lib/weaviate'
         DEFAULT_VECTORIZER_MODULE: 'none'
         CLUSTER_HOSTNAME: 'node1'
   ```
3. **Launch Weaviate:**
   ```bash
   docker-compose up -d
   ```
4. **Verify Startup:**
   Open your browser or run:
   ```bash
   curl http://localhost:8080/v1/.well-known/ready
   ```
   It should return `{"status":"READY"}`.

---

## 3. Final Verification
Once both services are running, you can start the Vella Server:

```bash
# Ensure your virtual environment is active
source .venv/bin/activate

# Run the server
uvicorn main:app --reload --host 0.0.0.0 --port 8001
```

If everything is correct, you will see:
`✅ All Shared Models (Llama-CPP & Whisper) Loaded Successfully!`
`🗺️ Active Routes:`
`...`
