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
    
    
    #One to one relationship with character
    character = models.OneToOneField(
        'characters.Character',
        on_delete=models.CASCADE,
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