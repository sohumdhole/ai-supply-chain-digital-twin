# Deployment Guide

This document describes how to deploy, run, and scale the **AI Supply Chain Digital Twin** application.

## 💻 Local Setup & Execution

### 1. Prerequisites
Ensure you have Python 3.8+ installed on your machine.

### 2. Installation
Clone the repository (or copy the folder), navigate to the directory, and install dependencies:
```bash
pip install -r requirements.txt
```

### 3. Run the Dashboard
Start the Streamlit application:
```bash
streamlit run app.py
```
This command will launch a local web server (usually at `http://localhost:8501`) and open it in your browser.

---

## 🐳 Docker Containerization

To run the application inside a container, create a `Dockerfile` in the root folder:

```dockerfile
# Use official lightweight Python image
FROM python:3.9-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Expose Streamlit default port
EXPOSE 8501

# Run the app
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

### Build and Run Docker Image:
```bash
docker build -t supply-chain-twin .
docker run -p 8501:8501 supply-chain-twin
```

---

## 🚀 Cloud Deployment

### 1. Streamlit Community Cloud (Easiest)
1. Push this project folder to a GitHub repository.
2. Sign in to [Streamlit Share](https://share.streamlit.io/).
3. Connect your GitHub account and click **"New app"**.
4. Select your repository, branch, and set the entry file to `app.py`.
5. Click **"Deploy"**.

### 2. Cloud Providers (AWS/GCP/Azure)
* **AWS App Runner / Google Cloud Run**: Both platforms allow deploying Docker containers automatically. You can push the Docker image to AWS ECR or Google Container Registry and configure the service to run on Port 8501.
* **EC2 / VM**: Set up a virtual machine, clone the repository, install Python/Docker, run the app, and expose port 8501 behind an Nginx reverse proxy.

---

## 📈 Scaling to Production

If you want to scale this prototype for enterprise use, consider the following modifications:

1. **Database Migration**:
   * Replace SQLite (`digital_twin.db`) with a robust client-server relational database like **PostgreSQL** or **MySQL**. Update the connection parameters in `digital_twin/database.py` using `psycopg2` or `SQLAlchemy`.
2. **Concurrent Runs**:
   * If multiple users run simulations simultaneously, SQLite might block due to lock contentions. Moving to PostgreSQL fully resolves this.
3. **LLM Integration**:
   * The AI Decision Engine current utilizes high-performance, deterministic rules and heuristics (which is fast, robust, and cost-effective). If you want to use Generative AI for generating recommendations, you can replace the logic in `digital_twin/ai_engine.py` with an OpenAI / Google Gemini API call, sending the computed TTS/TTR metrics as context in the prompt.
