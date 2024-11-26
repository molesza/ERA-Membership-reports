from django.db import models
import os

class MembershipUpload(models.Model):
    upload_date = models.DateTimeField(auto_now_add=True)
    file_name = models.CharField(max_length=255)
    month = models.CharField(max_length=20)
    year = models.IntegerField()
    file_content = models.BinaryField()  # Store the actual CSV file

    def __str__(self):
        return f"{self.month} {self.year}"

    class Meta:
        ordering = ['-year', '-upload_date']

class ComparisonReport(models.Model):
    current_upload = models.ForeignKey(MembershipUpload, on_delete=models.CASCADE, related_name='current_reports')
    previous_upload = models.ForeignKey(MembershipUpload, on_delete=models.CASCADE, related_name='previous_reports')
    generated_date = models.DateTimeField(auto_now_add=True)
    
    # Store the comparison results
    new_active_members = models.JSONField(default=list)
    new_free_members = models.JSONField(default=list)
    new_linked_members = models.JSONField(default=list)
    new_leads = models.JSONField(default=list)
    cancelled_members = models.JSONField(default=list)
    status_changes = models.JSONField(default=list)
    removed_members = models.JSONField(default=list)

    def __str__(self):
        return f"Comparison: {self.current_upload.month} {self.current_upload.year} vs {self.previous_upload.month} {self.previous_upload.year}"

    class Meta:
        ordering = ['-generated_date']
        unique_together = ['current_upload', 'previous_upload']

class Member(models.Model):
    upload = models.ForeignKey(MembershipUpload, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    surname = models.CharField(max_length=100)
    cell = models.CharField(max_length=20)
    email = models.EmailField(null=True, blank=True)
    status = models.CharField(max_length=20)
    mandate_signed = models.CharField(max_length=50)
    
    class Meta:
        indexes = [
            models.Index(fields=['cell']),
        ]

    def __str__(self):
        return f"{self.name} {self.surname}"
