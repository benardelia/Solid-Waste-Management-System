from rest_framework import serializers
from .models import ProjectArea, Household, Institute, CollectionRecord

class ProjectAreaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectArea
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')

class HouseholdSerializer(serializers.ModelSerializer):
    class Meta:
        model = Household
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')

class InstituteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Institute
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')

class CollectionRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = CollectionRecord
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')
