import graphene
from django.db.models import Q
from graphene_django import DjangoObjectType
from graphql import GraphQLError

from core.permissions import require_roles
from core.roles import REFERENCE_MANAGER_ROLES, ROLE_CHOICES

from .models import District, EntityType, PaymentMethod, Region, Ward


class OptionType(graphene.ObjectType):
    code = graphene.String(required=True)
    label = graphene.String(required=True)


def options(choices):
    return [OptionType(code=c, label=str(l)) for c, l in choices]


class RegionType(DjangoObjectType):
    class Meta:
        model = Region
        fields = ('id', 'name', 'postcode_prefix', 'districts')


class DistrictType(DjangoObjectType):
    ward_count = graphene.Int()

    class Meta:
        model = District
        fields = ('id', 'name', 'region', 'wards')

    def resolve_ward_count(self, info):
        return self.wards.count()


class WardType(DjangoObjectType):
    label = graphene.String(description='"Ward, postcode": the format the mobile dropdown shows')

    class Meta:
        model = Ward
        fields = ('id', 'name', 'postcode', 'district')

    def resolve_label(self, info):
        return str(self)


class EntityTypeType(DjangoObjectType):
    class Meta:
        model = EntityType
        fields = ('id', 'code', 'name', 'description', 'icon', 'counts_units', 'sort_order', 'is_active')


class PaymentMethodType(DjangoObjectType):
    logo_url = graphene.String()

    class Meta:
        model = PaymentMethod
        fields = ('id', 'code', 'name', 'description', 'color', 'sort_order', 'is_active')

    def resolve_logo_url(self, info):
        return info.context.build_absolute_uri(self.logo.url) if self.logo else None


class ReferenceDataType(graphene.ObjectType):
    """Every dropdown list the clients need, in one round-trip."""
    entity_types = graphene.List(graphene.NonNull(EntityTypeType), required=True)
    payment_methods = graphene.List(graphene.NonNull(PaymentMethodType), required=True)
    complaint_categories = graphene.List(graphene.NonNull('complaints.graphql.schema.ComplaintCategoryType'), required=True)
    roles = graphene.List(graphene.NonNull(OptionType), required=True)
    collection_statuses = graphene.List(graphene.NonNull(OptionType), required=True)
    waste_bin_options = graphene.List(graphene.NonNull(OptionType), required=True)
    complaint_statuses = graphene.List(graphene.NonNull(OptionType), required=True)
    complaint_priorities = graphene.List(graphene.NonNull(OptionType), required=True)
    complaint_sources = graphene.List(graphene.NonNull(OptionType), required=True)


WASTE_BIN_OPTIONS = (('yes', 'Yes'), ('no', 'No'))


class ReferenceQueries(graphene.ObjectType):
    reference_data = graphene.Field(
        ReferenceDataType, required=True,
        include_inactive=graphene.Boolean(default_value=False),
    )
    regions = graphene.List(graphene.NonNull(RegionType), required=True)
    districts = graphene.List(
        graphene.NonNull(DistrictType), required=True,
        region_id=graphene.Int(), search=graphene.String(),
    )
    wards = graphene.List(
        graphene.NonNull(WardType), required=True,
        district_id=graphene.Int(),
        district_name=graphene.String(description='Case-insensitive district name, e.g. from reverse geocoding'),
        search=graphene.String(),
    )

    @staticmethod
    def resolve_reference_data(root, info, include_inactive=False):
        from complaints.models import Complaint, ComplaintCategory
        from wastemanager.models import CollectionRecord

        def lookup(model):
            qs = model.objects.all()
            return qs if include_inactive else qs.filter(is_active=True)

        return ReferenceDataType(
            entity_types=lookup(EntityType),
            payment_methods=lookup(PaymentMethod),
            complaint_categories=lookup(ComplaintCategory),
            roles=options(ROLE_CHOICES),
            collection_statuses=options(CollectionRecord.STATUS_CHOICES),
            waste_bin_options=options(WASTE_BIN_OPTIONS),
            complaint_statuses=options(Complaint.STATUS_CHOICES),
            complaint_priorities=options(Complaint.PRIORITY_CHOICES),
            complaint_sources=options(Complaint.SOURCE_CHOICES),
        )

    @staticmethod
    @require_roles()
    def resolve_regions(root, info):
        return Region.objects.all()

    @staticmethod
    @require_roles()
    def resolve_districts(root, info, region_id=None, search=None):
        qs = District.objects.select_related('region')
        if region_id:
            qs = qs.filter(region_id=region_id)
        if search:
            qs = qs.filter(name__icontains=search)
        return qs

    @staticmethod
    @require_roles()
    def resolve_wards(root, info, district_id=None, district_name=None, search=None):
        qs = Ward.objects.select_related('district')
        if district_id:
            qs = qs.filter(district_id=district_id)
        elif district_name:
            qs = qs.filter(district__name__iexact=district_name.strip())
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(postcode__startswith=search))
        return qs


# ---------------------------------------------------------------- mutations

class LookupInput(graphene.InputObjectType):
    id = graphene.Int()
    code = graphene.String(required=True)
    name = graphene.String(required=True)
    description = graphene.String()
    sort_order = graphene.Int()
    is_active = graphene.Boolean()


class EntityTypeInput(LookupInput):
    icon = graphene.String()
    counts_units = graphene.Boolean()


class PaymentMethodInput(LookupInput):
    color = graphene.String()


def save_lookup(model, data):
    data = {k: v for k, v in dict(data).items() if v is not None}
    obj_id = data.pop('id', None)
    code = data['code'].strip().lower()
    if model.objects.filter(code=code).exclude(id=obj_id).exists():
        raise GraphQLError(f'Code "{code}" is already in use')
    data['code'] = code
    if obj_id:
        obj = model.objects.filter(id=obj_id).first()
        if obj is None:
            raise GraphQLError('Record not found')
        for key, value in data.items():
            setattr(obj, key, value)
        obj.save()
        return obj
    return model.objects.create(**data)


class SaveEntityType(graphene.Mutation):
    class Arguments:
        input = EntityTypeInput(required=True)

    entity_type = graphene.Field(EntityTypeType)

    @require_roles(*REFERENCE_MANAGER_ROLES)
    def mutate(self, info, input):
        return SaveEntityType(entity_type=save_lookup(EntityType, input))


class SavePaymentMethod(graphene.Mutation):
    class Arguments:
        input = PaymentMethodInput(required=True)

    payment_method = graphene.Field(PaymentMethodType)

    @require_roles(*REFERENCE_MANAGER_ROLES)
    def mutate(self, info, input):
        return SavePaymentMethod(payment_method=save_lookup(PaymentMethod, input))


class SaveDistrict(graphene.Mutation):
    class Arguments:
        id = graphene.Int()
        region_id = graphene.Int(required=True)
        name = graphene.String(required=True)

    district = graphene.Field(DistrictType)

    @require_roles(*REFERENCE_MANAGER_ROLES)
    def mutate(self, info, region_id, name, id=None):
        district = District.objects.filter(id=id).first() if id else District(region_id=region_id)
        if id and district is None:
            raise GraphQLError('District not found')
        district.region_id = region_id
        district.name = name.strip()
        district.save()
        return SaveDistrict(district=district)


class SaveWard(graphene.Mutation):
    class Arguments:
        id = graphene.Int()
        district_id = graphene.Int(required=True)
        name = graphene.String(required=True)
        postcode = graphene.String()

    ward = graphene.Field(WardType)

    @require_roles(*REFERENCE_MANAGER_ROLES)
    def mutate(self, info, district_id, name, id=None, postcode=''):
        ward = Ward.objects.filter(id=id).first() if id else Ward()
        if id and ward is None:
            raise GraphQLError('Ward not found')
        ward.district_id = district_id
        ward.name = name.strip()
        ward.postcode = (postcode or '').strip()
        ward.save()
        return SaveWard(ward=ward)


class DeleteWard(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)

    success = graphene.Boolean()

    @require_roles(*REFERENCE_MANAGER_ROLES)
    def mutate(self, info, id):
        deleted, _ = Ward.objects.filter(id=id).delete()
        return DeleteWard(success=bool(deleted))


class ReferenceMutations(graphene.ObjectType):
    save_entity_type = SaveEntityType.Field()
    save_payment_method = SavePaymentMethod.Field()
    save_district = SaveDistrict.Field()
    save_ward = SaveWard.Field()
    delete_ward = DeleteWard.Field()
