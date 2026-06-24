from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django_filters import rest_framework as filters
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from . import actions, dispatcher
from .models import MoistureReading, PumpAction, Configuration, ScheduledPumpAction, Schedule
from .serializers import (
    ConfigurationSerializer, MoistureReadingSerializer, PumpActionSerializer,
    ScheduledPumpActionSerializer, ScheduleSerializer,
)


class StrictQueryParamMixin:
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        allowed = set(self.filterset_class.get_filters().keys())
        unknown = set(request.query_params.keys()) - allowed
        if unknown:
            raise ValidationError(
                {"detail": f"Unknown query parameter(s): {', '.join(sorted(unknown))}"}
            )


class MoistureReadingFilter(filters.FilterSet):
    start = filters.DateTimeFilter(field_name='timestamp', lookup_expr='gte')
    end = filters.DateTimeFilter(field_name='timestamp', lookup_expr='lte')

    class Meta:
        model = MoistureReading
        fields = ['start', 'end']


class MoistureReadingViewSet(StrictQueryParamMixin, viewsets.ModelViewSet):
    queryset = MoistureReading.objects.all()
    serializer_class = MoistureReadingSerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = MoistureReadingFilter

    @action(detail=False, methods=['put'])
    def trigger(self, request):
        return actions.trigger_measurement()


class PumpActionFilter(filters.FilterSet):
    start = filters.DateTimeFilter(field_name='timestamp', lookup_expr='gte')
    end = filters.DateTimeFilter(field_name='timestamp', lookup_expr='lte')

    class Meta:
        model = PumpAction
        fields = ['start', 'end']


class PumpActionViewSet(StrictQueryParamMixin, viewsets.ModelViewSet):
    queryset = PumpAction.objects.all()
    serializer_class = PumpActionSerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = PumpActionFilter

    @action(detail=False, methods=['put'])
    def start(self, request):
        return actions.start_pump()

    @action(detail=False, methods=['put'])
    def stop(self, request):
        return actions.stop_pump()


class ConfigurationView(viewsets.ModelViewSet):
    queryset = Configuration.objects.all()
    serializer_class = ConfigurationSerializer

    def update(self, request, *args, **kwargs):
        response = super(viewsets.ModelViewSet, self).update(request, *args, **kwargs)
        actions.send_configuration(response.data)
        return response

    @action(detail=False, methods=['get'])
    def retrieve_from_arduino(self, request):
        return actions.retrieve_configuration()


class ScheduledPumpActionViewSet(viewsets.ModelViewSet):
    queryset = ScheduledPumpAction.objects.all()
    serializer_class = ScheduledPumpActionSerializer


class ScheduleFilter(filters.FilterSet):
    start = filters.DateFilter(field_name='schedule_date', lookup_expr='gte')
    end = filters.DateFilter(field_name='schedule_date', lookup_expr='lte')

    class Meta:
        model = Schedule
        fields = ['start', 'end']


class ScheduleViewSet(StrictQueryParamMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Schedule.objects.all()
    serializer_class = ScheduleSerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = ScheduleFilter


def _is_localhost(request):
    return request.META.get('REMOTE_ADDR') in ('127.0.0.1', '::1')


@csrf_exempt
@require_POST
def internal_tick(request):
    """Internal scheduler tick. Localhost-only.

    Mounted outside /api/ so it is not reachable through the nginx reverse proxy
    (and therefore not through ngrok); access is restricted to 127.0.0.1/::1.
    """
    if not _is_localhost(request):
        return JsonResponse({'detail': 'Forbidden'}, status=403)
    planned, pump_action = dispatcher.tick()
    return JsonResponse({'status': 'ok', 'planned': planned, "pump_action": pump_action})
