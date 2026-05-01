from django.db import models
from django.contrib.auth.models import User

class Conversation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=255, default="New Chat")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Notebook LLM: Store URLs/files loaded into the conversation context
    notebook_files = models.JSONField(
        blank=True,
        null=True,
        default=list,
        help_text='URLs and files loaded into Notebook LLM for this conversation'
    )

    def __str__(self):
        return f"{self.title} - {self.user.username if self.user else 'Anonymous'}"

    def add_notebook_file(self, file_info):
        """Add a file/URL to notebook_files if not already present."""
        if not self.notebook_files:
            self.notebook_files = []

        # Check if already exists by URL
        if isinstance(file_info, dict) and 'url' in file_info:
            existing = [f for f in self.notebook_files if isinstance(f, dict) and f.get('url') == file_info['url']]
            if existing:
                return False

        self.notebook_files.append(file_info)
        self.save(update_fields=['notebook_files', 'updated_at'])
        return True

    def remove_notebook_file(self, index):
        """Remove a file/URL from notebook_files by index."""
        if self.notebook_files and 0 <= index < len(self.notebook_files):
            self.notebook_files.pop(index)
            self.save(update_fields=['notebook_files', 'updated_at'])
            return True
        return False

    def clear_notebook_files(self):
        """Clear all notebook files."""
        self.notebook_files = []
        self.save(update_fields=['notebook_files', 'updated_at'])

    def update_title(self, new_title):
        """Update conversation title."""
        self.title = new_title[:255]  # Ensure max length
        self.save(update_fields=['title', 'updated_at'])

class Message(models.Model):
    ROLE_CHOICES = (
        ('user', 'User'),
        ('model', 'Model'),
    )
    conversation = models.ForeignKey(Conversation, related_name='messages', on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    thinking_process = models.TextField(blank=True, null=True)
    sources = models.TextField(blank=True, null=True)
    attachments = models.JSONField(blank=True, null=True, default=list, help_text='File attachments metadata')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.role}] {self.content[:50]}"


# ==================== SLIDE MODELS ====================

class SlideDeck(models.Model):
    """A presentation/slide deck container"""
    THEME_CHOICES = [
        ('modern', 'Modern Dark'),
        ('light', 'Clean Light'),
        ('gradient', 'Gradient Pop'),
        ('minimal', 'Minimal White'),
        ('corporate', 'Corporate Blue'),
        ('creative', 'Creative Purple'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='slide_decks')
    title = models.CharField(max_length=255, default="Untitled Presentation")
    description = models.TextField(blank=True, null=True)
    theme = models.CharField(max_length=20, choices=THEME_CHOICES, default='modern')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_public = models.BooleanField(default=False)
    aspect_ratio = models.CharField(max_length=10, default='16:9', choices=[
        ('16:9', '16:9 Widescreen'),
        ('4:3', '4:3 Standard'),
        ('21:9', '21:9 Ultrawide'),
    ])
    
    class Meta:
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"{self.title} - {self.user.username}"
    
    @property
    def slide_count(self):
        return self.slides.count()
    
    def get_theme_config(self):
        themes = {
            'modern': {'name': 'Modern Dark', 'bg': '#0f172a', 'text': '#f8fafc', 'accent': '#6366f1', 'secondary': '#1e293b'},
            'light': {'name': 'Clean Light', 'bg': '#ffffff', 'text': '#1e293b', 'accent': '#3b82f6', 'secondary': '#f1f5f9'},
            'gradient': {'name': 'Gradient Pop', 'bg': 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', 'text': '#ffffff', 'accent': '#fbbf24', 'secondary': 'rgba(255,255,255,0.1)'},
            'minimal': {'name': 'Minimal White', 'bg': '#fafafa', 'text': '#171717', 'accent': '#171717', 'secondary': '#e5e5e5'},
            'corporate': {'name': 'Corporate Blue', 'bg': '#ffffff', 'text': '#1e3a5f', 'accent': '#0066cc', 'secondary': '#e8f4fc'},
            'creative': {'name': 'Creative Purple', 'bg': '#1a0b2e', 'text': '#ffffff', 'accent': '#e056fd', 'secondary': '#2d1b4e'},
        }
        return themes.get(self.theme, themes['modern'])


class Slide(models.Model):
    """Individual slide within a deck"""
    LAYOUT_CHOICES = [
        ('title', 'Title Slide'),
        ('content', 'Content'),
        ('two-column', 'Two Column'),
        ('image-text', 'Image + Text'),
        ('text-image', 'Text + Image'),
        ('full-image', 'Full Image'),
        ('quote', 'Quote'),
        ('data', 'Data/Chart'),
        ('section', 'Section Divider'),
        ('blank', 'Blank'),
    ]
    
    deck = models.ForeignKey(SlideDeck, on_delete=models.CASCADE, related_name='slides')
    order = models.PositiveIntegerField(default=0)
    layout = models.CharField(max_length=20, choices=LAYOUT_CHOICES, default='content')
    content = models.JSONField(default=dict)
    custom_css = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['order']
    
    def __str__(self):
        title = self.content.get('title', '')[:50]
        return f"Slide {self.order + 1}: {title or 'Untitled'}"


class SlideExport(models.Model):
    """Track slide exports (PPTX, PDF)"""
    FORMAT_CHOICES = [
        ('pptx', 'PowerPoint'),
        ('pdf', 'PDF'),
        ('html', 'HTML'),
        ('images', 'Image Sequence'),
    ]
    
    deck = models.ForeignKey(SlideDeck, on_delete=models.CASCADE, related_name='exports')
    format = models.CharField(max_length=10, choices=FORMAT_CHOICES)
    file = models.FileField(upload_to='slide_exports/')
    file_size = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    download_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.deck.title} - {self.format.upper()}"


# ==================== USER PROFILE & PRO SUBSCRIPTION ====================

class UserProfile(models.Model):
    """Extended user profile for Pro subscription management"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    is_pro = models.BooleanField(default=False, help_text='User has active Pro subscription')
    pro_expiry_date = models.DateTimeField(null=True, blank=True, help_text='Pro subscription expiry date')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        status = "Pro" if self.is_pro_active else "Free"
        return f"{self.user.username} - {status}"

    @property
    def is_pro_active(self):
        """Check if user has active Pro subscription (not expired)"""
        if not self.is_pro or not self.pro_expiry_date:
            return False
        from django.utils import timezone
        return timezone.now() < self.pro_expiry_date

    def activate_pro(self, days=30):
        """Activate or extend Pro subscription"""
        from django.utils import timezone
        from datetime import timedelta

        self.is_pro = True

        # If already has active subscription, extend from expiry date
        # Otherwise, start from now
        if self.pro_expiry_date and self.pro_expiry_date > timezone.now():
            self.pro_expiry_date = self.pro_expiry_date + timedelta(days=days)
        else:
            self.pro_expiry_date = timezone.now() + timedelta(days=days)

        self.save(update_fields=['is_pro', 'pro_expiry_date', 'updated_at'])

    def deactivate_pro(self):
        """Deactivate Pro subscription (for failed payments, refunds, etc.)"""
        self.is_pro = False
        self.pro_expiry_date = None
        self.save(update_fields=['is_pro', 'pro_expiry_date', 'updated_at'])
