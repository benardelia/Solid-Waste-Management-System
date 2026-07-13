from django.contrib import admin
from .models import ProjectArea, Household, Institute, CollectionRecord

@admin.register(ProjectArea)
class ProjectAreaAdmin(admin.ModelAdmin):
    list_display = ('id', 'uid', 'name', 'monthly_fee', 'created_at')
    search_fields = ('name',)
    list_filter = ('created_at',)

@admin.register(Household)
class HouseholdAdmin(admin.ModelAdmin):
    list_display = ('id', 'uid', 'owner_name', 'house_number', 'ward', 'area', 'last_collection_status')
    search_fields = ('owner_name', 'house_number', 'district', 'ward', 'village')
    list_filter = ('area', 'last_collection_status', 'waste_bin_present')

@admin.register(Institute)
class InstituteAdmin(admin.ModelAdmin):
    list_display = ('id', 'uid', 'owners_name', 'house_number', 'ward', 'area')
    search_fields = ('owners_name', 'house_number', 'district', 'ward', 'village')
    list_filter = ('area', 'waste_bin_present')

@admin.register(CollectionRecord)
class CollectionRecordAdmin(admin.ModelAdmin):
    list_display = ('id', 'uid', 'worker', 'get_entity_name', 'status', 'amount_collected', 'timestamp')
    search_fields = ('worker__username', 'household__owner_name', 'institute__owners_name')
    list_filter = ('status', 'area', 'timestamp')

    def get_entity_name(self, obj):
        if obj.household:
            return f"Household: {obj.household.owner_name}"
        if obj.institute:
            return f"Institute: {obj.institute.owners_name}"
        return "Unknown"
    get_entity_name.short_description = 'Entity'
