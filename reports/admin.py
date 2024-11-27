from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.utils.crypto import get_random_string
from .models import MembershipUpload, ComparisonReport, Member
from django import forms

def generate_secure_password():
    """Generate a secure 12-character password with mixed case, numbers, and special characters."""
    chars = 'abcdefghijklmnopqrstuvwxyz'
    upper_chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    numbers = '0123456789'
    special_chars = '!@#$%^&*()_+-=[]{}|;:,.<>?'
    
    # Ensure at least one of each type
    password = [
        get_random_string(1, chars),
        get_random_string(1, upper_chars),
        get_random_string(1, numbers),
        get_random_string(1, special_chars),
    ]
    
    # Fill remaining 8 characters with a mix
    all_chars = chars + upper_chars + numbers + special_chars
    password.extend(get_random_string(8, all_chars))
    
    # Shuffle the password characters
    password_list = list(''.join(password))
    from random import shuffle
    shuffle(password_list)
    return ''.join(password_list)

class SimpleUserCreationForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('username',)

    def save(self, commit=True):
        user = super().save(commit=False)
        password = generate_secure_password()
        user.set_password(password)
        user._generated_password = password
        if commit:
            user.save()
        return user

class CustomUserAdmin(UserAdmin):
    add_form = SimpleUserCreationForm
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username',),
        }),
    )
    
    def response_add(self, request, obj, post_url_continue=None):
        """Show the generated password in the success message."""
        if hasattr(obj, '_generated_password'):
            self.message_user(request, 
                f'User "{obj.username}" was added successfully. '
                f'Generated password: {obj._generated_password}')
            delattr(obj, '_generated_password')
        return super().response_add(request, obj, post_url_continue)

# Unregister the default UserAdmin and register our custom one
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

@admin.register(MembershipUpload)
class MembershipUploadAdmin(admin.ModelAdmin):
    list_display = ('month', 'year', 'upload_date', 'file_name')
    list_filter = ('year', 'month')
    ordering = ('-year', '-upload_date')
    search_fields = ('month', 'year', 'file_name')

@admin.register(ComparisonReport)
class ComparisonReportAdmin(admin.ModelAdmin):
    list_display = ('get_comparison_title', 'generated_date')
    list_filter = ('generated_date',)
    ordering = ('-generated_date',)
    
    def get_comparison_title(self, obj):
        return f"{obj.current_upload.month} {obj.current_upload.year} vs {obj.previous_upload.month} {obj.previous_upload.year}"
    get_comparison_title.short_description = 'Comparison'

@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ('name', 'surname', 'cell', 'email', 'status', 'mandate_signed')
    list_filter = ('status', 'upload')
    search_fields = ('name', 'surname', 'cell', 'email')
    ordering = ('surname', 'name')
