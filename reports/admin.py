from django.contrib import admin
from .models import MembershipUpload, ComparisonReport, Member

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
