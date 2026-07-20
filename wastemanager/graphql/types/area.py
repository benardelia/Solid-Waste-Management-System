from graphene_django import DjangoObjectType
import graphene
from wastemanager.models import ProjectArea, Registration, CollectionRecord


class ProjectAreaType(DjangoObjectType):
    class Meta:
        model = ProjectArea
        fields = "__all__"


class RegistrationType(DjangoObjectType):
    """GraphQL type for the unified Registration model (household, shop, restaurant, etc.)."""

    last_collection_status = graphene.String()

    class Meta:
        model = Registration
        fields = "__all__"

    def resolve_last_collection_status(self, info):
        from django.utils import timezone

        if self.last_collection_date:
            days_since = (timezone.now() - self.last_collection_date).days
            if days_since >= 14:
                return 'missed'
            elif days_since >= 7:
                return 'pending'

        return self.last_collection_status


class CollectionRecordType(DjangoObjectType):
    class Meta:
        model = CollectionRecord
        fields = "__all__"
