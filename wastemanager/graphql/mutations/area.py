import graphene
from django.utils import timezone

from wastemanager.models import Registration, CollectionRecord
from wastemanager.graphql.types.area import RegistrationType, CollectionRecordType
from core.graphql.auth_decorator import authenticate_mutation


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
        try:
            worker = info.context.user
            record = CollectionRecord.objects.create(
                worker=worker,
                area_id=area_id,
                registration_id=registration_id,
                status=status,
                amount_collected=amount_collected,
                timestamp=timezone.now(),
            )

            # Update the registration's last collection tracking fields
            if registration_id:
                reg = Registration.objects.get(id=registration_id)
                reg.last_collection_status = status
                reg.last_collection_date   = timezone.now()
                reg.save(update_fields=['last_collection_status', 'last_collection_date'])

            return LogCollection(collection=record, success=True)
        except Exception as e:
            import logging
            logging.error(f"Error logging collection: {e}")
            return LogCollection(success=False)


class WastemanagerMutation(graphene.ObjectType):
    create_registration     = CreateRegistration.Field()
    update_collection_status = UpdateCollectionStatus.Field()
    log_collection          = LogCollection.Field()
