import graphene
from wastemanager.models import Household, CollectionRecord
from wastemanager.graphql.types.area import HouseholdType, CollectionRecordType
from core.graphql.auth_decorator import authenticate_mutation

class CreateHousehold(graphene.Mutation):
    class Arguments:
        area_id = graphene.Int(required=True)
        owner_name = graphene.String(required=True)
        district = graphene.String(required=True)
        ward = graphene.String(required=True)
        village = graphene.String(required=True)
        latitude = graphene.Float(required=True)
        longitude = graphene.Float(required=True)
        waste_bin_present = graphene.String(required=True)
        uid = graphene.String(required=False)

    household = graphene.Field(HouseholdType)
    success = graphene.Boolean()

    @authenticate_mutation
    def mutate(self, info, area_id, owner_name, district, ward, village, latitude, longitude, waste_bin_present, uid=None):
        kwargs = {
            'area_id': area_id,
            'owner_name': owner_name,
            'district': district,
            'ward': ward,
            'village': village,
            'latitude': latitude,
            'longitude': longitude,
            'waste_bin_present': waste_bin_present
        }
        if uid:
            kwargs['uid'] = uid
            
        household = Household.objects.create(**kwargs)
        return CreateHousehold(household=household, success=True)

class UpdateCollectionStatus(graphene.Mutation):
    class Arguments:
        record_id = graphene.Int(required=True)
        status = graphene.String(required=True)

    collection = graphene.Field(CollectionRecordType)
    success = graphene.Boolean()

    @authenticate_mutation
    def mutate(self, info, record_id, status):
        try:
            record = CollectionRecord.objects.get(id=record_id)
            record.status = status
            record.save()
            return UpdateCollectionStatus(collection=record, success=True)
        except CollectionRecord.DoesNotExist:
            return UpdateCollectionStatus(success=False)

from django.utils import timezone

class LogCollection(graphene.Mutation):
    class Arguments:
        area_id = graphene.Int(required=True)
        status = graphene.String(required=True)
        amount_collected = graphene.Float(required=True)
        household_id = graphene.Int(required=False)
        institute_id = graphene.Int(required=False)

    collection = graphene.Field(CollectionRecordType)
    success = graphene.Boolean()

    @authenticate_mutation
    def mutate(self, info, area_id, status, amount_collected, household_id=None, institute_id=None):
        try:
            worker = info.context.user
            kwargs = {
                'worker': worker,
                'area_id': area_id,
                'status': status,
                'amount_collected': amount_collected,
                'timestamp': timezone.now()
            }
            if household_id:
                kwargs['household_id'] = household_id
            if institute_id:
                kwargs['institute_id'] = institute_id
                
            record = CollectionRecord.objects.create(**kwargs)
            
            # Update household last_collection_status
            if household_id:
                h = Household.objects.get(id=household_id)
                h.last_collection_status = status
                h.save()
            
            return LogCollection(collection=record, success=True)
        except Exception as e:
            import logging
            logging.error(f"Error logging collection: {e}")
            return LogCollection(success=False)

class RegisterInstitute(graphene.Mutation):
    class Arguments:
        district = graphene.String(required=True)
        ward = graphene.String(required=True)
        village = graphene.String(required=True)
        house_number = graphene.String(required=True)
        postcode = graphene.String(required=True)
        owners_name = graphene.String(required=True)
        owners_contact = graphene.String(required=True)
        waste_bin_present = graphene.String(required=True)
        latitude = graphene.Float(required=True)
        longitude = graphene.Float(required=True)
        area_id = graphene.Int(required=True)

    success = graphene.Boolean()

    @authenticate_mutation
    def mutate(self, info, district, ward, village, house_number, postcode, owners_name, owners_contact, waste_bin_present, latitude, longitude, area_id):
        try:
            Institute.objects.create(
                district=district,
                ward=ward,
                village=village,
                house_number=house_number,
                postcode=postcode,
                owners_name=owners_name,
                owners_contact=owners_contact,
                waste_bin_present=waste_bin_present,
                latitude=latitude,
                longitude=longitude,
                area_id=area_id
            )
            return RegisterInstitute(success=True)
        except Exception as e:
            import logging
            logging.error(f"Error registering institute: {e}")
            return RegisterInstitute(success=False)

class WastemanagerMutation(graphene.ObjectType):
    create_household = CreateHousehold.Field()
    update_collection_status = UpdateCollectionStatus.Field()
    log_collection = LogCollection.Field()
    register_institute = RegisterInstitute.Field()
