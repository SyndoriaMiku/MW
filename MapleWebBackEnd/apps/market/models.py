from django.db import models

# Create your models here.

class Trade(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('cancelled', 'Cancelled')
    ]

    sender = models.ForeignKey('users.GameUser', on_delete=models.CASCADE, related_name='sent_trades')
    receiver = models.ForeignKey('users.GameUser', on_delete=models.CASCADE, related_name='received_trades')
    
    #Lumis to be traded
    sender_lumis = models.PositiveIntegerField(default=0)
    receiver_lumis = models.PositiveIntegerField(default=0)
    
    #Check time of trade
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    
    def __str__(self):
        return f"{self.sender.username} to {self.receiver.username}"
    
class TradeItem(models.Model):
    trade = models.ForeignKey('market.Trade', on_delete=models.CASCADE, related_name='items')
    item = models.ForeignKey('inventory.InventoryItem', on_delete=models.CASCADE)
    is_sender = models.BooleanField() #True if the item is from the sender, False if the item is from the receiver
    
    def __str__(self):
        role = 'Sender' if self.is_sender else 'Receiver'
        return f"{role}: {self.item.name}"
    
class Listing(models.Model):
    #User listing this item
    seller = models.ForeignKey('users.GameUser', on_delete=models.CASCADE, related_name='listings')
    #Item being listed
    item = models.ForeignKey('inventory.InventoryItem', on_delete=models.CASCADE, related_name='listings')
    
    #Price of the item (Lumis)
    price = models.PositiveIntegerField()
    #Status of the listing
    is_active = models.BooleanField(default=True)
    
    #Quantity if item stackable
    quantity = models.PositiveIntegerField(default=1)
    
    def __str__(self):
        return f"{self.item.name} listed by {self.seller.username}"
    
class Transaction(models.Model):
    #ID of the transaction
    id = models.AutoField(primary_key=True)
    #Link to the listing
    listing = models.ForeignKey('market.Listing', on_delete=models.CASCADE, related_name='transactions')
    #Buyer of the item
    buyer = models.ForeignKey('users.GameUser', on_delete=models.CASCADE, related_name='transactions')
    #Seller of the item
    seller = models.ForeignKey('users.GameUser', on_delete=models.CASCADE, related_name='sales')
    #Transaction time
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Transaction {self.id}"