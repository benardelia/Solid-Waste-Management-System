from rest_framework import viewsets
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Sum, F, Case, When
from django.utils.dateparse import parse_date
from rest_framework.permissions import IsAuthenticated

from .models import ProjectArea, Registration, CollectionRecord
from .serializers import (
    ProjectAreaSerializer,
    RegistrationSerializer,
    CollectionRecordSerializer,
)


class ProjectAreaViewSet(viewsets.ModelViewSet):
    queryset = ProjectArea.objects.all()
    serializer_class = ProjectAreaSerializer
    permission_classes = [IsAuthenticated]


class RegistrationViewSet(viewsets.ModelViewSet):
    """
    Unified viewset for all entity types (household, shop, restaurant, etc.).
    Filter by entity_type to narrow results, e.g. ?entity_type=household
    """
    queryset = Registration.objects.all()
    serializer_class = RegistrationSerializer
    filterset_fields = ['area', 'entity_type', 'waste_bin_present', 'last_collection_status']
    permission_classes = [IsAuthenticated]


class CollectionRecordViewSet(viewsets.ModelViewSet):
    queryset = CollectionRecord.objects.all()
    serializer_class = CollectionRecordSerializer
    filterset_fields = ['area', 'registration', 'status', 'worker']
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        with transaction.atomic():
            record = serializer.save()

            # Update the linked registration's last collection status
            if record.registration:
                record.registration.last_collection_status = record.status
                record.registration.last_collection_date = record.timestamp
                record.registration.save(
                    update_fields=['last_collection_status', 'last_collection_date', 'updated_at']
                )


class AreaStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, area_id):
        try:
            area = ProjectArea.objects.get(id=area_id)
        except ProjectArea.DoesNotExist:
            return Response({"error": "Area not found"}, status=404)

        # Time filtering
        start_date_str = request.query_params.get('start_date')
        end_date_str   = request.query_params.get('end_date')

        collection_qs = CollectionRecord.objects.filter(area=area)

        if start_date_str:
            start_date = parse_date(start_date_str)
            if start_date:
                collection_qs = collection_qs.filter(timestamp__gte=start_date)

        if end_date_str:
            end_date = parse_date(end_date_str)
            if end_date:
                collection_qs = collection_qs.filter(timestamp__lte=end_date)

        # Expected amount:
        # For households: fee * number_of_units; for all others: fee (1 unit)
        expected = Registration.objects.filter(area=area).aggregate(
            total=Sum(
                Case(
                    When(
                        monthly_fee_override__isnull=False,
                        then=F('monthly_fee_override') * F('number_of_units'),
                    ),
                    default=area.monthly_fee * F('number_of_units'),
                )
            )
        )['total'] or 0

        collected = (
            collection_qs.filter(status='collected')
            .aggregate(total=Sum('amount_collected'))['total'] or 0
        )

        performance    = (collected / expected * 100) if expected > 0 else 0
        unpaid_count   = collection_qs.filter(status='unpaid').count()
        missed_count   = collection_qs.filter(status='missed').count()

        return Response({
            "areaId":                  area.id,
            "areaName":                area.name,
            "expectedAmount":          expected,
            "collectedAmount":         collected,
            "collectionPercentage":    round(performance, 2),
            "unpaidCollectionsCount":  unpaid_count,
            "missedCollectionsCount":  missed_count,
        })
