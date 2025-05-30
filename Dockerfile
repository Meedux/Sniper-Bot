FROM python:3.9-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# Install Chrome and other dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libwayland-client0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    xvfb \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Chromium as a fallback for ARM64 architecture or Google Chrome for AMD64
RUN apt-get update && \
    if [ "$(dpkg --print-architecture)" = "arm64" ] || [ "$(dpkg --print-architecture)" = "aarch64" ]; then \
      echo "Installing Chromium for ARM64 architecture..." && \
      apt-get install -y chromium && \
      ln -s /usr/bin/chromium /usr/bin/google-chrome && \
      echo "Using Chromium as a replacement for Chrome"; \
    else \
      echo "Installing Chrome for AMD64 architecture..." && \
      wget -q https://dl-ssl.google.com/linux/linux_signing_key.pub -O /usr/share/keyrings/google-chrome.key && \
      echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.key] https://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
      apt-get update && \
      apt-get install -y google-chrome-stable && \
      echo "Successfully installed Google Chrome"; \
    fi && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set up working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code and chromedriver
COPY . .

# Install the extracted chromedriver file 
RUN if [ -f chromedriver ]; then \
      cp chromedriver /usr/local/bin/chromedriver && \
      chmod +x /usr/local/bin/chromedriver && \
      echo "Successfully installed chromedriver"; \
    else \
      echo "chromedriver file not found, container may not work correctly"; \
    fi

# Create a script to run Chrome with Xvfb for headless operation
RUN echo '#!/bin/bash\nXvfb :99 -screen 0 1920x1080x24 &\nexport DISPLAY=:99\nexec "$@"' > /entrypoint.sh \
    && chmod +x /entrypoint.sh

# Set the entrypoint
ENTRYPOINT ["/entrypoint.sh"]

# Default command to run
CMD ["python", "one.py"]