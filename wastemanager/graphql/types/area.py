from graphene_django import DjangoObjectType
import graphene
from wastemanager.models import ProjectArea, Household, Institute, CollectionRecord

class ProjectAreaType(DjangoObjectType):
    class Meta:
        model = ProjectArea
        fields = "__all__"

class HouseholdType(DjangoObjectType):
    last_collection_status = graphene.String()

    class Meta:
        model = Household
        fields = "__all__"

    def resolve_last_collection_status(self, info):
        import datetime
        from django.utils import timezone

        if self.last_collection_date:
            days_since = (timezone.now() - self.last_collection_date).days
            if days_since >= 14:
                return 'missed'
            elif days_since >= 7:
                return 'pending'
        
        return self.last_collection_status

class InstituteType(DjangoObjectType):
    class Meta:
        model = Institute
        fields = "__all__"

class CollectionRecordType(DjangoObjectType):
    class Meta:
        model = CollectionRecord
        fields = "__all__"
