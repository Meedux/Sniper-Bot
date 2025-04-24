# Reddit Account Sniper Bot

A sophisticated automation tool designed to monitor and purchase Reddit accounts that match your specified criteria. The bot runs in Docker, making it platform-independent and easy to deploy.

![Reddit Account Sniper Bot](https://img.shields.io/badge/Reddit-Account%20Sniper-FF4500?style=for-the-badge&logo=reddit&logoColor=white)

## Features

- **Automated Monitoring**: Constantly monitors Reddit account listings
- **Customizable Criteria**: Filter by karma threshold, price, and specific keywords
- **Docker Support**: Run in an isolated container on any platform
- **CAPTCHA Handling**: Built-in handling for reCAPTCHA challenges
- **Headless Operation**: Can run without visible browser windows
- **Debug Mode**: Captures screenshots and page HTML for troubleshooting
- **Test Mode**: Simulates purchases without completing transactions
- **Detailed Logging**: Comprehensive logging of all actions

## Prerequisites

### System Requirements

- Docker and Docker Compose installed
  - [Docker Installation Guide](https://docs.docker.com/get-docker/)
  - [Docker Compose Installation Guide](https://docs.docker.com/compose/install/)
- At least 2GB of available RAM
- Internet connection

### Files Required

The following files should exist in your project directory:
- `one.py` - Main script file
- `chromedriver` - Linux ChromeDriver binary (no extension)
- `docker-compose.yml` - Docker Compose configuration
- `Dockerfile` - Docker build instructions
- `reddit_sniper_config.json` - Configuration file (can be auto-generated)
- `requirements.txt` - Python dependencies

## Installation

1. **Clone or download this repository**:
   ```bash
   git clone https://github.com/yourusername/reddit-account-sniper-bot.git
   cd reddit-account-sniper-bot
   ```

2. **Ensure ChromeDriver is available**:
   
   The bot requires a Linux version of ChromeDriver (without extension) in the project directory. If you don't have it:
   
   - Download the ChromeDriver for Linux that matches your Chrome version from:
     https://googlechromelabs.github.io/chrome-for-testing/
   - Extract the `chromedriver` file to your project directory
   - Make sure it has no file extension

3. **Build the Docker container**:
   ```bash
   docker-compose build
   ```

## Usage

### 1. Edit the Configuration File

Before running the bot, customize the `reddit_sniper_config.json` file with your preferences. The configuration varies slightly depending on which script you're using (`one.py` or `test.py`).

#### Configuration for `one.py` (Recommended)

This version of the bot focuses on finding accounts based on karma thresholds:

```json
{
    "target_url": "https://redaccs.com/#acc",
    "refresh_interval": 30,
    "min_karma": 1000,
    "max_price": 50.0,
    "headless": false,
    "test_mode": true,
    "debug_mode": true,
    "coupon_code": "YOUR_COUPON_HERE",
    "credentials": {
        "email": "your_email@example.com",
        "password": "your_password"
    },
    "checkout_info": {
        "first_name": "John",
        "last_name": "Doe"
    }
}
```

#### Configuration for `test.py`

This version of the bot focuses on finding accounts based on specific keywords:

```json
{
    "target_url": "https://redaccs.com/shop/",
    "refresh_interval": 30,
    "min_karma": 1000,
    "max_price": 50.0,
    "headless": false,
    "test_mode": true,
    "debug_mode": true,
    "search_keyword": "50x",
    "coupon_code": "YOUR_COUPON_HERE",
    "credentials": {
        "email": "your_email@example.com",
        "password": "your_password"
    },
    "checkout_info": {
        "first_name": "John",
        "last_name": "Doe"
    }
}
```

**Configuration Options**:

| Option | Description | Used in |
|--------|-------------|---------|
| `target_url` | URL of the page where Reddit accounts are listed | Both scripts |
| `refresh_interval` | How often to refresh the page (in seconds) | Both scripts |
| `min_karma` | Minimum karma threshold for account selection | Both scripts |
| `max_price` | Maximum price you're willing to pay (set to 0 for no limit) | Both scripts |
| `headless` | Set to `true` to run without visible browser windows | Both scripts |
| `test_mode` | Set to `true` to simulate purchases without completing transactions | Both scripts |
| `debug_mode` | Set to `true` to save screenshots and HTML for troubleshooting | Both scripts |
| `search_keyword` | Specific keyword to look for in account listings (e.g., "50x" for accounts with 50k+ karma) | `test.py` only |
| `coupon_code` | Coupon code to apply during checkout | Both scripts |
| `credentials` | Your login credentials for the website | Both scripts |
| `checkout_info` | Your personal information for checkout | Both scripts |

### 2. Run the Docker Container

Start the bot using Docker Compose:

```bash
docker-compose up
```

This will:
1. Create and start the Docker container
2. Mount your configuration and output directories
3. Start the bot with your specified settings
4. Display logs in real-time

For running in the background:

```bash
docker-compose up -d
```

To view logs while running in the background:

```bash
docker-compose logs -f
```

### 3. Watch for Results

The bot performs the following actions:
1. Initializes and logs into the website
2. Monitors the page for Reddit accounts matching your criteria
3. When a matching account is found, it:
   - Clicks on the "Buy" button
   - Applies any coupon code you've specified
   - Fills in checkout information
   - Solves any CAPTCHA challenges
   - Completes the purchase (unless in test mode)

**Monitoring Output**:

- The terminal displays detailed logs of the bot's actions
- All logs are saved to `logs/reddit_sniper_YYYYMMDD.log`
- If debug mode is enabled, screenshots and HTML are saved on errors

### 4. Modify Bot Behavior

You can stop the bot at any time by pressing `Ctrl+C` or running:

```bash
docker-compose down
```

To change settings:
1. Stop the container
2. Edit the `reddit_sniper_config.json` file
3. Restart the container with `docker-compose up`

### 5. Understanding Log Output

Log entries include:
- Timestamp
- Log level (INFO, WARNING, ERROR)
- Detailed message about the bot's actions

Example log entries:
```
2025-04-24 12:34:56 - INFO - Bot initialized with target URL: https://redaccs.com/shop/
2025-04-24 12:34:57 - INFO - Chrome started successfully in Docker container
2025-04-24 12:34:58 - INFO - Looking for Buy Now button...
2025-04-24 12:35:05 - INFO - Found matching account with 55K karma, price: $45.00
```

## Troubleshooting

### Common Issues

1. **ChromeDriver Compatibility**:
   - If you see errors related to ChromeDriver, ensure you're using the Linux version without file extension
   - The version should match the Chrome version in the Docker container

2. **JavaScript Execution Errors**:
   - Some JavaScript errors are normal in Docker environments
   - The bot has been configured to work around these limitations

3. **"User data directory is already in use" Error**:
   - Stop all running containers with `docker-compose down`
   - If the issue persists, restart Docker

4. **CAPTCHA Solving Failures**:
   - Enable debug mode to get screenshots of CAPTCHA challenges
   - Check if NextCaptcha API key is valid

### Debugging Tools

When `debug_mode` is enabled, the bot will save:
- Screenshots at key points and when errors occur
- HTML source of the page when errors occur

These files are saved to the mounted volumes:
- `screenshots/` - Contains all captured screenshots
- `logs/` - Contains detailed log files

## Customization

### Using Different Account Providers

To use a different Reddit account provider:
1. Update the `target_url` in your config file
2. You may need to modify the selectors in `one.py` if the website has a different structure

### Advanced Settings

For advanced users, you can modify additional settings by editing `one.py`:
- Custom user agents
- Additional Chrome options
- Wait time configurations
- CAPTCHA handling strategies

## Security Considerations

- Your credentials are stored in plain text in the config file
- Use environment variables or a secure storage solution in production
- Run the bot in a controlled environment
- Be cautious when providing payment information

---

**Happy Account Sniping!**