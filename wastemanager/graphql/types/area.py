from graphene_django import DjangoObjectType
import graphene
from wastemanager.models import ProjectArea, Registration, CollectionRecord


class ProjectAreaType(DjangoObjectType):
    registration_count = graphene.Int()
    worker_count = graphene.Int()

    class Meta:
        model = ProjectArea
        fields = ("id", "uid", "name", "monthly_fee", "created_at", "updated_at")

    def resolve_registration_count(self, info):
        if hasattr(self, 'n_registrations'):
            return self.n_registrations
        return self.registrations.count()

    def resolve_worker_count(self, info):
        if hasattr(self, 'n_workers'):
            return self.n_workers
        return self.assigned_users.filter(user_type='worker').count()


class RegistrationType(DjangoObjectType):
    """GraphQL type for the unified Registration model (household, shop, restaurant, etc.)."""

    last_collection_status = graphene.String()
    entity_type_label = graphene.String()
    effective_monthly_fee = graphene.Float(description='(override or area fee) × units')

    class Meta:
        model = Registration
        fields = "__all__"
        convert_choices_to_enum = False

    def resolve_last_collection_status(self, info):
        from django.utils import timezone

        if self.last_collection_date:
            days_since = (timezone.now() - self.last_collection_date).days
            if days_since >= 14:
                return 'missed'
            elif days_since >= 7:
                return 'pending'

        return self.last_collection_status

    def resolve_entity_type_label(self, info):
        return self.entity_type_label

    def resolve_effective_monthly_fee(self, info):
        fee = self.monthly_fee_override if self.monthly_fee_override is not None else self.area.monthly_fee
        return float(fee * self.number_of_units)


class CollectionRecordType(DjangoObjectType):
    class Meta:
        model = CollectionRecord
        fields = "__all__"
        convert_choices_to_enum = False
