# Admin Files Refactoring - Remove All Autocomplete Fields

## Issue
The `autocomplete_fields` feature requires that the referenced models have `search_fields` defined in their admin classes. Many models don't have admin classes registered or don't have search_fields, causing "not registered" errors.

## Solution
Remove all `autocomplete_fields` from all admin files. Django will use regular dropdown selects instead, which work fine for small to medium datasets.

## Files to Update

Remove lines containing `autocomplete_fields =` from these files:

### ✅ Already Fixed:
- apps/characters/admin.py (3 instances removed)

### 🔄 Need to Fix:
1. apps/classes/admin.py (1 instance)
2. apps/items/admin.py (5 instances)
3. apps/inventory/admin.py (2 instances)
4. apps/battles/admin.py (2 instances)
5. apps/market/admin.py (5 instances)
6. apps/skilles/admin.py (1 instance)
7. apps/party/admin.py (5 instances)
8. apps/quests/admin.py (4 instances)
9. apps/world/admin.py (2 instances)
10. apps/shops/admin.py (5 instances)

## Manual Steps

For each admin.py file, remove lines that match:
```python
autocomplete_fields = [...]
```
or
```python
autocomplete_fields = (...)
```

## Alternative: Add search_fields to All Models

If you want to keep autocomplete_fields (recommended for better UX with large datasets), you need to add `search_fields` to every model admin that's referenced. This includes:

- Character
- GameUser (User)
- CharacterClass
- Job
- ItemTemplate
- InventoryItem
- SkillTemplate
- Party
- EnemyTemplate
- Quest
- DungeonTemplate
- ShopCategory
- SpecialShopItem
- And all other referenced models...

This is a much larger task.

## Recommendation

**Remove all autocomplete_fields for now** to get migrations working. You can add them back later with proper search_fields after the initial migration is complete.
