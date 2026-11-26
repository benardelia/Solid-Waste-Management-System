from django.contrib import admin

from .models import Complaint, ComplaintCategory, ComplaintUpdate


@admin.register(ComplaintCategory)
class ComplaintCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'default_priority', 'sla_hours', 'is_active')
    list_editable = ('is_active',)


class ComplaintUpdateInline(admin.TabularInline):
    model = ComplaintUpdate
    extra = 0
    fields = ('author', 'message', 'old_status', 'new_status', 'is_internal', 'created_at')
    readonly_fields = ('created_at',)


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ('reference', 'title', 'category', 'area', 'priority', 'status', 'assigned_to', 'created_at')
    list_filter = ('status', 'priority', 'category', 'area')
    search_fields = ('reference', 'title', 'complainant_name', 'complainant_phone')
    readonly_fields = ('reference', 'created_at', 'updated_at', 'resolved_at')
    inlines = [ComplaintUpdateInline]
