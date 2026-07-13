from graphene_django import DjangoObjectType
from wastemanager.models import ProjectArea, Household, Institute, CollectionRecord

class ProjectAreaType(DjangoObjectType):
    class Meta:
        model = ProjectArea
        fields = "__all__"

class HouseholdType(DjangoObjectType):
    class Meta:
        model = Household
        fields = "__all__"

class InstituteType(DjangoObjectType):
    class Meta:
        model = Institute
        fields = "__all__"

class CollectionRecordType(DjangoObjectType):
    class Meta:
        model = CollectionRecord
        fields = "__all__"
