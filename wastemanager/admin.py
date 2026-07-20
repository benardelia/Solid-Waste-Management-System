from django.contrib import admin
from .models import ProjectArea, Registration, CollectionRecord


@admin.register(ProjectArea)
class ProjectAreaAdmin(admin.ModelAdmin):
    list_display = ('id', 'uid', 'name', 'monthly_fee', 'created_at')
    search_fields = ('name',)
    list_filter = ('created_at',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'uid', 'entity_type', 'owner_name',
        'house_number', 'ward', 'area', 'last_collection_status',
    )
    search_fields = ('owner_name', 'house_number', 'district', 'ward', 'village')
    list_filter = ('entity_type', 'area', 'last_collection_status', 'waste_bin_present')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(CollectionRecord)
class CollectionRecordAdmin(admin.ModelAdmin):
    list_display = ('id', 'uid', 'worker', 'get_entity_name', 'status', 'amount_collected', 'timestamp')
    search_fields = ('worker__username', 'registration__owner_name')
    list_filter = ('status', 'area', 'timestamp')
    readonly_fields = ('created_at', 'updated_at')

    def get_entity_name(self, obj):
        if obj.registration:
            return f"{obj.registration.get_entity_type_display()}: {obj.registration.owner_name}"
        return "Unknown"

    get_entity_name.short_description = 'Entity'
