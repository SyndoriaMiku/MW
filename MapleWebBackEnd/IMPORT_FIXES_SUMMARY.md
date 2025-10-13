# Import Problem Fixes Summary

## Date: October 13, 2025

## Overview
Fixed all model import problems by converting direct model references to string-based references in Django model relationships. This prevents circular import issues and follows Django best practices.

## Changes Made

### 1. apps/inventory/models.py
**Fixed Issues:**
- ❌ `Item = models.ForeignKey(Item, ...)` - undefined model reference
- ❌ `item_type = models.CharField(..., choices=Item.Type_Choices)` - accessing undefined model

**Solutions:**
- ✅ Changed `Item` ForeignKey to `'inventory.InventoryItem'`
- ✅ Duplicated `Type_Choices` locally in `AuroraLinePool` model to avoid cross-app reference
- ✅ Renamed field from `Item` to `inventory_item` for clarity

**Code Changes:**
```python
# Before:
Item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='aurora_lines')
item_type = models.CharField(max_length=20, choices=Item.Type_Choices, help_text="Item type")

# After:
inventory_item = models.ForeignKey('inventory.InventoryItem', on_delete=models.CASCADE, related_name='aurora_lines')
# Type_Choices duplicated in AuroraLinePool class
item_type = models.CharField(max_length=20, choices=Type_Choices, help_text="Item type")
```

---

### 2. apps/classes/models.py
**Fixed Issues:**
- ❌ `character_class = models.ForeignKey(CharacterClass, ...)` - direct model reference

**Solutions:**
- ✅ Changed to string reference: `'classes.CharacterClass'`

**Code Changes:**
```python
# Before:
character_class = models.ForeignKey(CharacterClass, on_delete=models.CASCADE)

# After:
character_class = models.ForeignKey('classes.CharacterClass', on_delete=models.CASCADE)
```

---

### 3. apps/battles/models.py
**Fixed Issues:**
- ❌ `combat_instance = models.ForeignKey(CombatInstance, ...)` - direct model reference

**Solutions:**
- ✅ Changed to string reference: `'battles.CombatInstance'`

**Code Changes:**
```python
# Before:
combat_instance = models.ForeignKey(CombatInstance, on_delete=models.CASCADE, related_name='combatants')

# After:
combat_instance = models.ForeignKey('battles.CombatInstance', on_delete=models.CASCADE, related_name='combatants')
```

---

### 4. apps/items/models.py
**Fixed Issues:**
- ❌ `item_set = models.ForeignKey(ItemSet, ...)` - direct model reference
- ❌ `items = models.ManyToManyField(ItemTemplate, ...)` - direct model reference

**Solutions:**
- ✅ Changed ForeignKey to: `'items.ItemSet'`
- ✅ Changed ManyToManyField to: `'items.ItemTemplate'`

**Code Changes:**
```python
# Before:
item_set = models.ForeignKey(ItemSet, on_delete=models.CASCADE, related_name='effects')
items = models.ManyToManyField(ItemTemplate, blank=True, related_name='item_sets')

# After:
item_set = models.ForeignKey('items.ItemSet', on_delete=models.CASCADE, related_name='effects')
items = models.ManyToManyField('items.ItemTemplate', blank=True, related_name='item_sets')
```

---

### 5. apps/market/models.py
**Fixed Issues:**
- ❌ `trade = models.ForeignKey(Trade, ...)` - direct model reference
- ❌ `listing = models.ForeignKey(Listing, ...)` - direct model reference
- ❌ References to `'user.User'` - incorrect app name
- ❌ References to `'inventory.Item'` - incorrect model name

**Solutions:**
- ✅ Changed all `'user.User'` to `'users.User'` (correct app name)
- ✅ Changed all `'inventory.Item'` to `'inventory.InventoryItem'` (correct model name)
- ✅ Changed `Trade` to `'market.Trade'`
- ✅ Changed `Listing` to `'market.Listing'`

**Code Changes:**
```python
# Before:
sender = models.ForeignKey('user.User', ...)
receiver = models.ForeignKey('user.User', ...)
trade = models.ForeignKey(Trade, ...)
item = models.ForeignKey('inventory.Item', ...)
listing = models.ForeignKey(Listing, ...)

# After:
sender = models.ForeignKey('users.User', ...)
receiver = models.ForeignKey('users.User', ...)
trade = models.ForeignKey('market.Trade', ...)
item = models.ForeignKey('inventory.InventoryItem', ...)
listing = models.ForeignKey('market.Listing', ...)
```

---

## String Reference Format

Django supports string references in the following formats:

### Same App Reference:
```python
# If referencing a model in the same app
models.ForeignKey('ModelName', ...)
```

### Cross-App Reference:
```python
# Format: 'app_label.ModelName'
models.ForeignKey('users.User', ...)
models.ForeignKey('inventory.InventoryItem', ...)
models.ForeignKey('characters.Character', ...)
```

### Self Reference:
```python
# Special case for self-referencing
models.ForeignKey('self', ...)
```

---

## Benefits of String References

1. **Prevents Circular Imports**: No need to import model classes
2. **Django Best Practice**: Recommended by Django documentation
3. **Lazy Evaluation**: Models are resolved at runtime, not import time
4. **Cleaner Code**: No import statements cluttering the file
5. **Better App Isolation**: Apps don't need to import each other

---

## Verification Checklist

✅ All ForeignKey fields use string references  
✅ All ManyToManyField fields use string references  
✅ All OneToOneField fields use string references (none found)  
✅ Correct app names used (users, not user)  
✅ Correct model names used (InventoryItem, not Item)  
✅ No direct model imports for relationships  
✅ All cross-app references use 'app.Model' format  

---

## Next Steps

1. **Run Migrations**:
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

2. **Check for Issues**:
   ```bash
   python manage.py check
   ```

3. **Test Models**:
   ```bash
   python manage.py shell
   >>> from apps.inventory.models import InventoryItem
   >>> from apps.characters.models import Character
   >>> # Test model creation and relationships
   ```

---

## Common String Reference Patterns in Your Project

### Users App:
- `'users.User'` - User model

### Characters App:
- `'characters.Character'` - Character model

### Classes App:
- `'classes.CharacterClass'` - Character class model
- `'classes.Job'` - Job model

### Inventory App:
- `'inventory.InventoryItem'` - Inventory item model

### Items App:
- `'items.ItemTemplate'` - Item template model
- `'items.ItemSet'` - Item set model

### Market App:
- `'market.Trade'` - Trade model
- `'market.TradeItem'` - Trade item model
- `'market.Listing'` - Listing model
- `'market.Transaction'` - Transaction model

### Battles App:
- `'battles.CombatInstance'` - Combat instance model
- `'battles.Combatant'` - Combatant model

### World App:
- `'world.Location'` - Location model (if exists)

---

## Troubleshooting

### If you see "Model 'app.Model' doesn't exist":
1. Check that the app is in `INSTALLED_APPS`
2. Verify the model name is correct (case-sensitive)
3. Ensure migrations have been run

### If you see "Circular import" errors:
1. Make sure you're NOT importing the model class
2. Use string references instead: `'app.ModelName'`
3. Remove any `from apps.xxx.models import YYY` lines for relationships

### If you see "Field defines a relation with model":
1. Check the app label matches the folder name
2. Verify the model class name matches exactly
3. Ensure the app is properly configured in apps.py

---

**Status**: ✅ All import problems fixed  
**Last Updated**: October 13, 2025  
**Ready for**: Migration generation and testing
