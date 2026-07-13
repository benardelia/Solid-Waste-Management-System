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

class WastemanagerMutation(graphene.ObjectType):
    create_household = CreateHousehold.Field()
    update_collection_status = UpdateCollectionStatus.Field()
