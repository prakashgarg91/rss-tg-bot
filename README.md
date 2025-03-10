# RSS to Telegram Bot

This service fetches RSS feeds and posts updates to multiple Telegram channels on a regular schedule.

## Features

- Parse RSS feeds from configured URLs
- Post updates to multiple Telegram channels (up to 20+)
- Track already posted items to avoid duplicates
- Run on a 2-hour schedule
- Deployed on Heroku

## Setup Instructions

### Prerequisites

- Python 3.9+
- A Telegram bot token (get from [@BotFather](https://t.me/botfather))
- RSS feed URLs
- Telegram channel IDs where the bot is an admin

### Environment Variables

Configure the following environment variables:

- `TELEGRAM_BOT_TOKEN`: Your Telegram bot token
- `RSS_FEED_URL`: URL of the RSS feed to parse
- `TELEGRAM_CHANNEL_IDS`: Comma-separated list of channel IDs (e.g., "@channel1,@channel2")
- `CHECK_INTERVAL`: (Optional) Interval in seconds between checks (default: 7200 = 2 hours)

### Local Development

1. Clone this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set environment variables
4. Run the script:
   ```bash
   python scheduler.py
   ```

### Heroku Deployment
[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/prakashgarg91/YOUR_REPO_NAME)

1. Create a Heroku account if you don't have one
2. Install the Heroku CLI
3. Initialize a Git repository:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   ```
4. Create a new Heroku app:
   ```bash
   heroku create your-app-name
   ```
5. Set the required environment variables:
   ```bash
   heroku config:set TELEGRAM_BOT_TOKEN=your_token
   heroku config:set RSS_FEED_URL=https://example.com/rss
   heroku config:set TELEGRAM_CHANNEL_IDS=@channel1,@channel2,@channel3
   ```
6. Deploy to Heroku:
   ```bash
   git push heroku main
   ```
7. Scale the worker dyno:
   ```bash
   heroku ps:scale worker=1
   ```

## Monitoring and Maintenance

- View logs with: `heroku logs --tail`
- Update configuration: `heroku config:set VARIABLE=value`
- Restart the worker: `heroku restart`

## Adding More Channels

To add more channels:
1. Add your bot to the new channel as an administrator
2. Update the `TELEGRAM_CHANNEL_IDS` environment variable with the new channel ID
3. Restart the worker: `heroku restart`

## Troubleshooting

If you encounter issues:
- Ensure the bot is an administrator in all channels
- Check the RSS feed URL is valid and accessible
- Review the logs for any error messages: `heroku logs --tail`
- Verify all environment variables are correctly set
