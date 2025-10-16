# Quick Fix: Remove All Autocomplete Fields

## Quick Command to Remove All

Run this command from the MapleWebBackEnd directory:

```bash
# Backup first
cp -r apps apps_backup

# Remove all autocomplete_fields lines from all admin.py files
find apps -name "admin.py" -type f -exec sed -i '' '/autocomplete_fields/d' {} \;
```

## What This Does

Removes ALL lines containing `autocomplete_fields` from all admin.py files in the apps directory.

## After Running

Run migrations:
```bash
python manage.py makemigrations
python manage.py migrate
```

## To Restore Autocomplete Later

1. Add `search_fields` to all model admins:
```python
search_fields = ('name', 'id')  # or relevant fields
```

2. Then add back `autocomplete_fields` where needed

## Affected Files

- apps/classes/admin.py
- apps/items/admin.py  
- apps/inventory/admin.py
- apps/battles/admin.py
- apps/market/admin.py
- apps/skilles/admin.py
- apps/party/admin.py
- apps/quests/admin.py
- apps/world/admin.py
- apps/shops/admin.py
