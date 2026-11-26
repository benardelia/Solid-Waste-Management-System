from django.contrib import admin

from .models import District, EntityType, PaymentMethod, Region, Ward


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ('name', 'postcode_prefix')
    search_fields = ('name',)


@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    list_display = ('name', 'region')
    list_filter = ('region',)
    search_fields = ('name',)


@admin.register(Ward)
class WardAdmin(admin.ModelAdmin):
    list_display = ('name', 'postcode', 'district')
    list_filter = ('district__region', 'district')
    search_fields = ('name', 'postcode')


@admin.register(EntityType, PaymentMethod)
class LookupAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'sort_order', 'is_active')
    list_editable = ('sort_order', 'is_active')
    search_fields = ('name', 'code')
