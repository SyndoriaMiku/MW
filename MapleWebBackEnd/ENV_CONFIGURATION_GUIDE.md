# Environment Configuration Setup

## Overview
This project uses `python-decouple` to manage environment variables securely. This allows you to keep sensitive information out of version control and makes it easy to configure different environments (development, staging, production).

## Files Created

### 1. `.env` (Local Configuration - NOT in Git)
Contains your actual configuration values. **This file is already added to `.gitignore` and will NOT be committed to Git.**

**Location:** `/MapleWebBackEnd/.env`

### 2. `.env.example` (Template - IN Git)
A template file showing what variables are needed. Share this with your team.

**Location:** `/MapleWebBackEnd/.env.example`

## Configuration Variables

### Django Core Settings
- `SECRET_KEY`: Django secret key (keep this secret!)
- `DEBUG`: Enable/disable debug mode (True/False)
- `ALLOWED_HOSTS`: Comma-separated list of allowed hosts

### Database Configuration
- `DATABASE_ENGINE`: Database backend (default: sqlite3)
- `DATABASE_NAME`: Database name or path
- `DATABASE_USER`: Database username (PostgreSQL/MySQL)
- `DATABASE_PASSWORD`: Database password (PostgreSQL/MySQL)
- `DATABASE_HOST`: Database host (PostgreSQL/MySQL)
- `DATABASE_PORT`: Database port (PostgreSQL/MySQL)

### CORS Settings
- `CORS_ALLOWED_ORIGINS`: Comma-separated list of allowed origins
- `CORS_ALLOW_ALL_ORIGINS`: Allow all origins (True/False)
- `CORS_ALLOW_CREDENTIALS`: Allow credentials (True/False)

## Usage Examples

### Reading Variables in settings.py

```python
from decouple import config, Csv

# String value
SECRET_KEY = config('SECRET_KEY')

# Boolean value
DEBUG = config('DEBUG', default=True, cast=bool)

# Comma-separated list
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost', cast=Csv())

# Integer value
PORT = config('PORT', default=8000, cast=int)

# Float value
TAX_RATE = config('TAX_RATE', default=0.1, cast=float)
```

### Reading Variables in Other Files

```python
from decouple import config

# In any Python file
max_characters = config('MAX_CHARACTERS_PER_USER', default=5, cast=int)
starting_gold = config('DEFAULT_STARTING_GOLD', default=1000, cast=int)
```

## Setup Instructions

### For New Developers

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd MapleWebBackEnd
   ```

2. **Copy the example file**
   ```bash
   cp .env.example .env
   ```

3. **Edit `.env` with your values**
   ```bash
   nano .env  # or use your preferred editor
   ```

4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

5. **Run migrations**
   ```bash
   python manage.py migrate
   ```

### Switching to PostgreSQL

Update your `.env` file:

```env
DATABASE_ENGINE=django.db.backends.postgresql
DATABASE_NAME=mapledb
DATABASE_USER=your_username
DATABASE_PASSWORD=your_password
DATABASE_HOST=localhost
DATABASE_PORT=5432
```

Then install PostgreSQL adapter:
```bash
pip install psycopg2-binary
```

## Security Best Practices

### ✅ DO:
- Keep `.env` file in `.gitignore`
- Use strong, unique SECRET_KEY in production
- Set `DEBUG=False` in production
- Use environment-specific `.env` files
- Generate new SECRET_KEY for production

### ❌ DON'T:
- Commit `.env` file to Git
- Share your `.env` file publicly
- Use the same SECRET_KEY across environments
- Store passwords in plain text in code

## Generating a New SECRET_KEY

Run this in Django shell:

```python
from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())
```

Or in terminal:
```bash
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

## Production Deployment

For production servers (Heroku, AWS, etc.), set environment variables through the platform's interface:

### Heroku
```bash
heroku config:set SECRET_KEY=your-secret-key
heroku config:set DEBUG=False
heroku config:set DATABASE_URL=postgresql://...
```

### Docker
Use docker-compose environment or .env file:
```yaml
services:
  web:
    environment:
      - SECRET_KEY=${SECRET_KEY}
      - DEBUG=${DEBUG}
```

### AWS/Azure
Set environment variables in the service configuration (Elastic Beanstalk, App Service, etc.)

## Troubleshooting

### Error: "SECRET_KEY not found"
- Make sure `.env` file exists in the same directory as `manage.py`
- Check that `python-decouple` is installed: `pip install python-decouple`
- Verify `.env` file has `SECRET_KEY=...` line

### Error: "UndefinedValueError"
- The variable is required but not found in `.env`
- Add the variable to your `.env` file or provide a default value in `config()`

### Values not updating
- Restart your Django server after changing `.env` file
- Check for typos in variable names (case-sensitive)

## Additional Resources

- [python-decouple Documentation](https://github.com/HBNetwork/python-decouple)
- [Django Settings Best Practices](https://docs.djangoproject.com/en/stable/topics/settings/)
- [12 Factor App - Config](https://12factor.net/config)

## Custom Game Settings (Examples)

You can add game-specific settings to `.env`:

```env
# Game Configuration
MAX_CHARACTERS_PER_USER=5
DEFAULT_STARTING_GOLD=1000
DEFAULT_STARTING_LEVEL=1
BATTLE_TIMEOUT_SECONDS=300
MAX_PARTY_SIZE=4
DAILY_LOGIN_REWARD=50
ENERGY_REFILL_RATE=1  # per minute
MAX_ENERGY=100
```

Then use them in your code:

```python
from decouple import config

# In views or models
max_chars = config('MAX_CHARACTERS_PER_USER', default=5, cast=int)
starting_gold = config('DEFAULT_STARTING_GOLD', default=1000, cast=int)
battle_timeout = config('BATTLE_TIMEOUT_SECONDS', default=300, cast=int)
```

---

**Last Updated:** October 13, 2025  
**Status:** ✅ Configured and Ready
