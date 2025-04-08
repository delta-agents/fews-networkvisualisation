FROM ubuntu:22.04 

# Install dependencies
RUN apt-get update && apt-get install -y curl

# Install Pixi
RUN curl -fsSL https://pixi.sh/install.sh | bash
ENV PATH="/root/.pixi/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy project files
ADD pixi.toml /app/pixi.toml
ADD ./talkwithfews /app/talkwithfews
ADD ./logs /app/logs
ADD ./app /app/app

# Create empty dirs to be filled
RUN mkdir /app/db
RUN mkdir /app/env


# Install dependencies
RUN pixi install

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

ENTRYPOINT ["pixi", "run", "docker"]