from rest_framework import viewsets
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Sum, F, Case, When
from django.utils.dateparse import parse_date
from rest_framework.permissions import IsAuthenticated

from .models import ProjectArea, Household, Institute, CollectionRecord
from .serializers import (
    ProjectAreaSerializer, 
    HouseholdSerializer, 
    InstituteSerializer, 
    CollectionRecordSerializer
)

class ProjectAreaViewSet(viewsets.ModelViewSet):
    queryset = ProjectArea.objects.all()
    serializer_class = ProjectAreaSerializer
    permission_classes = [IsAuthenticated]

class HouseholdViewSet(viewsets.ModelViewSet):
    queryset = Household.objects.all()
    serializer_class = HouseholdSerializer
    filterset_fields = ['area', 'waste_bin_present', 'last_collection_status']
    permission_classes = [IsAuthenticated]

class InstituteViewSet(viewsets.ModelViewSet):
    queryset = Institute.objects.all()
    serializer_class = InstituteSerializer
    filterset_fields = ['area', 'waste_bin_present']
    permission_classes = [IsAuthenticated]

class CollectionRecordViewSet(viewsets.ModelViewSet):
    queryset = CollectionRecord.objects.all()
    serializer_class = CollectionRecordSerializer
    filterset_fields = ['area', 'household', 'institute', 'status', 'worker']
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        with transaction.atomic():
            record = serializer.save()
            
            # Update the related household's last collection status
            if record.household:
                record.household.last_collection_status = record.status
                record.household.save(update_fields=['last_collection_status', 'updated_at', 'updated_by'])


class AreaStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, area_id):
        try:
            area = ProjectArea.objects.get(id=area_id)
        except ProjectArea.DoesNotExist:
            return Response({"error": "Area not found"}, status=404)
        
        # Time filtering
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')
        
        # Determine the base collection queryset
        collection_qs = CollectionRecord.objects.filter(area=area)
        
        if start_date_str:
            start_date = parse_date(start_date_str)
            if start_date:
                collection_qs = collection_qs.filter(timestamp__gte=start_date)
                
        if end_date_str:
            end_date = parse_date(end_date_str)
            if end_date:
                collection_qs = collection_qs.filter(timestamp__lte=end_date)
        
        # Expected Amount = (Project area amount * number of households) + (institutes)
        # Note: If a household has an override, use the override * number_of_household (or just override if it covers all).
        # We assume override is per-registration. We'll use:
        # Household expected = Sum( (fee_override OR area.monthly_fee) * number_of_household )
        household_expected = Household.objects.filter(area=area).aggregate(
            total=Sum(
                Case(
                    When(monthly_fee_override__isnull=False, then=F('monthly_fee_override') * F('number_of_household')),
                    default=area.monthly_fee * F('number_of_household')
                )
            )
        )['total'] or 0
        
        institute_expected = Institute.objects.filter(area=area).aggregate(
            total=Sum(
                Case(
                    When(monthly_fee_override__isnull=False, then=F('monthly_fee_override')),
                    default=area.monthly_fee
                )
            )
        )['total'] or 0
        
        total_expected = household_expected + institute_expected
        
        # Collected Amount based on time filter
        collected = collection_qs.filter(status='collected').aggregate(total=Sum('amount_collected'))['total'] or 0
        
        # Collection Percentage (Performance)
        performance = (collected / total_expected * 100) if total_expected > 0 else 0
        
        # You could also add other stats here like missed collections, unpaid count, etc.
        unpaid_count = collection_qs.filter(status='unpaid').count()
        missed_count = collection_qs.filter(status='missed').count()
        
        return Response({
            "areaId": area.id,
            "areaName": area.name,
            "expectedAmount": total_expected,
            "collectedAmount": collected,
            "collectionPercentage": round(performance, 2),
            "unpaidCollectionsCount": unpaid_count,
            "missedCollectionsCount": missed_count,
        })
