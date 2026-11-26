import logging
from decimal import Decimal

import graphene
from django.db import transaction
from django.db.models import ProtectedError
from django.utils import timezone
from graphql import GraphQLError

from wastemanager.models import ProjectArea, Registration, CollectionRecord
from wastemanager.graphql.types.area import ProjectAreaType, RegistrationType, CollectionRecordType
from core.graphql.auth_decorator import authenticate_mutation
from core.permissions import require_roles
from core.roles import AREA_MANAGER_ROLES, STAFF_ROLES

logger = logging.getLogger(__name__)


def validate_entity_type(code):
    from reference.models import EntityType
    if not EntityType.objects.filter(code=code, is_active=True).exists():
        raise GraphQLError(f'Unknown entity type "{code}"')
    return code


def validate_collection_status(status):
    if status not in dict(CollectionRecord.STATUS_CHOICES):
        raise GraphQLError(f'Invalid collection status "{status}"')
    return status


class CreateRegistration(graphene.Mutation):
    """
    Create any type of registration: household, shop, restaurant, institute, etc.
    Pass `entityType` to specify the kind (defaults to 'household').
    """

    class Arguments:
        entity_type       = graphene.String(required=False, default_value='household')
        area_id           = graphene.Int(required=True)
        owner_name        = graphene.String(required=True)
        owners_contact    = graphene.String(required=False)
        district          = graphene.String(required=True)
        ward              = graphene.String(required=True)
        village           = graphene.String(required=True)
        house_number      = graphene.String(required=False, default_value='')
        postcode          = graphene.String(required=False, default_value='')
        latitude          = graphene.Float(required=True)
        longitude         = graphene.Float(required=True)
        waste_bin_present = graphene.String(required=True)
        number_of_units   = graphene.Int(required=False, default_value=1)
        uid               = graphene.String(required=False)

    registration = graphene.Field(RegistrationType)
    success      = graphene.Boolean()

    @authenticate_mutation
    def mutate(
        self, info,
        entity_type, area_id, owner_name, district, ward, village,
        latitude, longitude, waste_bin_present,
        owners_contact=None, house_number='', postcode='',
        number_of_units=1, uid=None,
    ):
        kwargs = dict(
            entity_type=entity_type,
            area_id=area_id,
            owner_name=owner_name,
            owners_contact=owners_contact,
            district=district,
            ward=ward,
            village=village,
            house_number=house_number,
            postcode=postcode,
            latitude=latitude,
            longitude=longitude,
            waste_bin_present=waste_bin_present,
            number_of_units=number_of_units,
        )
        if uid:
            kwargs['uid'] = uid
            # Offline retries resend the same uid: return the existing record instead of failing.
            existing = Registration.objects.filter(uid=uid).first()
            if existing:
                return CreateRegistration(registration=existing, success=True)

        validate_entity_type(entity_type)
        if not ProjectArea.objects.filter(id=area_id).exists():
            raise GraphQLError('Project area not found')
        registration = Registration.objects.create(**kwargs)
        return CreateRegistration(registration=registration, success=True)


class UpdateCollectionStatus(graphene.Mutation):
    class Arguments:
        record_id = graphene.Int(required=True)
        status    = graphene.String(required=True)

    collection = graphene.Field(CollectionRecordType)
    success    = graphene.Boolean()

    @authenticate_mutation
    def mutate(self, info, record_id, status):
        validate_collection_status(status)
        try:
            record        = CollectionRecord.objects.get(id=record_id)
            record.status = status
            record.save()
            return UpdateCollectionStatus(collection=record, success=True)
        except CollectionRecord.DoesNotExist:
            return UpdateCollectionStatus(success=False)


class LogCollection(graphene.Mutation):
    class Arguments:
        area_id          = graphene.Int(required=True)
        status           = graphene.String(required=True)
        amount_collected = graphene.Float(required=True)
        registration_id  = graphene.Int(required=False)

    collection = graphene.Field(CollectionRecordType)
    success    = graphene.Boolean()

    @authenticate_mutation
    def mutate(self, info, area_id, status, amount_collected, registration_id=None):
        validate_collection_status(status)
        if amount_collected < 0:
            raise GraphQLError('Amount collected cannot be negative')
        try:
            with transaction.atomic():
                now = timezone.now()
                record = CollectionRecord.objects.create(
                    worker=info.context.user,
                    area_id=area_id,
                    registration_id=registration_id,
                    status=status,
                    amount_collected=amount_collected,
                    timestamp=now,
                )

                # Update the registration's last collection tracking fields
                if registration_id:
                    Registration.objects.filter(id=registration_id).update(
                        last_collection_status=status, last_collection_date=now,
                    )

            return LogCollection(collection=record, success=True)
        except Exception as e:
            logger.exception("Error logging collection: %s", e)
            return LogCollection(success=False)


# ------------------------------------------------------------ admin portal

class SaveProjectArea(graphene.Mutation):
    """Create (no id) or update a project area."""

    class Arguments:
        id = graphene.Int()
        name = graphene.String(required=True)
        monthly_fee = graphene.Float(required=True)

    area = graphene.Field(ProjectAreaType)
    success = graphene.Boolean()

    @require_roles(*AREA_MANAGER_ROLES)
    def mutate(self, info, name, monthly_fee, id=None):
        if monthly_fee < 0:
            raise GraphQLError('Monthly fee cannot be negative')
        name = name.strip()
        if ProjectArea.objects.filter(name__iexact=name).exclude(id=id).exists():
            raise GraphQLError(f'An area named "{name}" already exists')
        area = ProjectArea.objects.filter(id=id).first() if id else ProjectArea()
        if id and area is None:
            raise GraphQLError('Area not found')
        area.name = name
        area.monthly_fee = Decimal(str(monthly_fee))
        area.save()
        return SaveProjectArea(area=area, success=True)


class DeleteProjectArea(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)

    success = graphene.Boolean()
    message = graphene.String()

    @require_roles(*AREA_MANAGER_ROLES)
    def mutate(self, info, id):
        area = ProjectArea.objects.filter(id=id).first()
        if area is None:
            raise GraphQLError('Area not found')
        if area.registrations.exists() or area.collections.exists():
            # Deleting would cascade and silently wipe billing history.
            raise GraphQLError('This area has registrations or collection history and cannot be deleted')
        try:
            area.delete()
        except ProtectedError:
            raise GraphQLError('This area is still referenced and cannot be deleted')
        return DeleteProjectArea(success=True, message='Area deleted')


class RegistrationInput(graphene.InputObjectType):
    entity_type = graphene.String()
    area_id = graphene.Int()
    owner_name = graphene.String()
    owners_contact = graphene.String()
    district = graphene.String()
    ward = graphene.String()
    village = graphene.String()
    house_number = graphene.String()
    postcode = graphene.String()
    waste_bin_present = graphene.String()
    latitude = graphene.Float()
    longitude = graphene.Float()
    number_of_units = graphene.Int()
    monthly_fee_override = graphene.Float()
    clear_fee_override = graphene.Boolean(description='Set true to remove the custom fee')


class UpdateRegistration(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
        input = RegistrationInput(required=True)

    registration = graphene.Field(RegistrationType)
    success = graphene.Boolean()

    @require_roles(*STAFF_ROLES)
    def mutate(self, info, id, input):
        reg = Registration.objects.filter(id=id).first()
        if reg is None:
            raise GraphQLError('Registration not found')
        data = {k: v for k, v in dict(input).items() if v is not None}
        if data.pop('clear_fee_override', False):
            reg.monthly_fee_override = None
        if 'entity_type' in data:
            validate_entity_type(data['entity_type'])
        if 'area_id' in data and not ProjectArea.objects.filter(id=data['area_id']).exists():
            raise GraphQLError('Project area not found')
        if data.get('number_of_units', 1) < 1:
            raise GraphQLError('Number of units must be at least 1')
        if data.get('monthly_fee_override', 0) < 0:
            raise GraphQLError('Monthly fee cannot be negative')
        if 'monthly_fee_override' in data:
            data['monthly_fee_override'] = Decimal(str(data['monthly_fee_override']))
        for key, value in data.items():
            setattr(reg, key, value)
        reg.save()
        return UpdateRegistration(registration=reg, success=True)


class DeleteRegistration(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)

    success = graphene.Boolean()

    @require_roles(*AREA_MANAGER_ROLES)
    def mutate(self, info, id):
        reg = Registration.objects.filter(id=id).first()
        if reg is None:
            raise GraphQLError('Registration not found')
        if reg.collections.exists():
            raise GraphQLError('This registration has collection history and cannot be deleted')
        reg.delete()
        return DeleteRegistration(success=True)


class WastemanagerMutation(graphene.ObjectType):
    create_registration     = CreateRegistration.Field()
    update_collection_status = UpdateCollectionStatus.Field()
    log_collection          = LogCollection.Field()
    save_project_area       = SaveProjectArea.Field()
    delete_project_area     = DeleteProjectArea.Field()
    update_registration     = UpdateRegistration.Field()
    delete_registration     = DeleteRegistration.Field()
