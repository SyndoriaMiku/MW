from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager


# Create your models here.

class UserManager(BaseUserManager):
    """
    Custom user manager
    """
    def create_user(self, username, email, password=None):
        if not email:
            raise ValueError('Users must have an email address')
        if not username:
            raise ValueError('Users must have a username')
        if not password:
            raise ValueError('Users must have a password')
        
        email = self.normalize_email(email)
        user = self.model(username=username, email=email)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, username, email, password=None):
        user = self.create_user(username, email, password)
        user.is_admin = True
        user.is_superuser = True
        user.is_staff = True
        user.save(using=self._db)
        return user
        
class GameUser(AbstractBaseUser):
    """
    Custom user model
    """
    username = models.CharField(max_length=255, unique=True)
    email = models.EmailField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    
    lumis = models.PositiveIntegerField(default=0) #Lumis currency
    nova = models.PositiveIntegerField(default=0) #Nova currency
    
    
    #One to one relationship with character. Deleting the character must not
    #delete the account, so the user simply loses it.
    character = models.OneToOneField(
        'characters.Character',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='user'
        )
    objects = UserManager()
    
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']
    
    class Meta:
        app_label = 'users'
        verbose_name = 'Game User'
        verbose_name_plural = 'Game Users'
    
    def __str__(self):
        return self.username
    
    def has_perm(self, perm, obj=None):
        """Does the user have a specific permission?"""
        return self.is_admin or self.is_superuser
    
    def has_module_perms(self, app_label):
        """Does the user have permissions to view the app `app_label`?"""
        return self.is_admin or self.is_superuser
    
    def has_admin_permissions(self):
        return self.is_admin


class NovaTransaction(models.Model):
    """
    One change to a user's Nova, the premium currency players get for
    donating. Every change goes through apps.users.nova_service, so the
    ledger and GameUser.nova always agree.
    """
    class Kind(models.TextChoices):
        DONATION = 'donation', 'Donation'
        PURCHASE = 'purchase', 'Shop purchase'
        ADJUSTMENT = 'adjustment', 'Admin adjustment'

    user = models.ForeignKey(GameUser, on_delete=models.PROTECT, related_name='nova_transactions')
    kind = models.CharField(max_length=20, choices=Kind.choices)
    amount = models.IntegerField(help_text="Positive adds Nova, negative takes it away")
    balance_after = models.PositiveIntegerField(editable=False)
    reference = models.CharField(
        max_length=100, null=True, blank=True, unique=True,
        help_text="Donation/payment reference (e.g. the Ko-fi ID). Each can be credited only once.",
    )
    description = models.CharField(max_length=200, blank=True, help_text="Shown to the player, e.g. '2x Potion'")
    note = models.TextField(blank=True, help_text="Internal note, not shown to the player")
    created_by = models.ForeignKey(
        GameUser, on_delete=models.SET_NULL, null=True, blank=True, editable=False, related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Nova Transaction'
        verbose_name_plural = 'Nova Transactions'
        ordering = ['-created_at', '-id']

    def clean(self):
        from .nova_service import validate_nova_change

        # Blank means "no reference"; NULLs never clash with each other.
        self.reference = (self.reference or '').strip() or None
        if self.user_id is None or self.amount is None or not self.kind:
            return
        error = validate_nova_change(self.user, self.amount, self.kind)
        if error:
            raise ValidationError({'amount': error})

    def __str__(self):
        return f"{self.user} {self.amount:+d} Nova ({self.get_kind_display()})"