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
        
        username = self.model.normalize_username(username)
        email = self.normalize_email(email)
        user = self.model(username=username, email=email)
        user.set_password(password)
        user.save(using=self._db)
        return user
    def create_superuser(self, username, email, password=None):
        user = self.create_user(username, password, email)
        user.is_admin = True
        user.is_superuser = True
        user.save(using=self._db)
        return user
        
class User(AbstractBaseUser):
    """
    Custom user model
    """
    username = models.CharField(max_length=255, unique=True)
    email = models.EmailField(max_length=255, unique=True)
    password = models.CharField(max_length=128)
    is_active = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)
    
    lumis = models.PositiveIntegerField(default=0) #Lumis currency
    
    
    #One to one relationship with character
    character = models.OneToOneField(
        'Character',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='user'
        )
    objects = UserManager()
    
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']
    
    def __str__(self):
        return self.username
    
    def is_admin(self):
        return self.is_admin