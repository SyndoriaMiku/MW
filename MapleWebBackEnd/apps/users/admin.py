from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django import forms
from .models import GameUser


class UserCreationForm(forms.ModelForm):
    """Form for creating new users"""
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Password confirmation', widget=forms.PasswordInput)

    class Meta:
        model = GameUser
        fields = ('username', 'email')

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords don't match")
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class UserChangeForm(forms.ModelForm):
    """Form for updating users"""
    password = ReadOnlyPasswordHashField()

    class Meta:
        model = GameUser
        fields = ('username', 'email', 'password', 'is_active', 'is_admin', 'lumis', 'nova')

    def clean_password(self):
        return self.initial["password"]


@admin.register(GameUser)
class UserAdmin(BaseUserAdmin):
    """Admin interface for User model"""
    form = UserChangeForm
    add_form = UserCreationForm

    list_display = ('username', 'email', 'lumis', 'nova', 'is_active', 'is_admin', 'last_login')
    list_filter = ('is_admin', 'is_active')
    
    fieldsets = (
        (None, {'fields': ('username', 'email', 'password')}),
        ('Permissions', {'fields': ('is_admin', 'is_active')}),
        ('Currency', {'fields': ('lumis', 'nova')}),
        ('Character', {'fields': ('character',)}),
        ('Important dates', {'fields': ('last_login',)}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2'),
        }),
    )
    
    search_fields = ('username', 'email')
    ordering = ('-last_login',)
    filter_horizontal = ()
    
    readonly_fields = ('last_login',)
    
    def has_module_permission(self, request):
        return request.user.is_superuser or request.user.is_admin
