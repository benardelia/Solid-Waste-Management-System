from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProjectAreaViewSet,
    RegistrationViewSet,
    CollectionRecordViewSet,
    AreaStatsView,
)

router = DefaultRouter()
router.register(r'areas',         ProjectAreaViewSet)
router.register(r'registrations', RegistrationViewSet)
router.register(r'collections',   CollectionRecordViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('stats/area/<int:area_id>/', AreaStatsView.as_view(), name='area-stats'),
]
