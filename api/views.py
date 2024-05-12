from django_filters import rest_framework as filters
from rest_framework import viewsets
from rest_framework.decorators import action

from . import actions
from .models import MoistureReading, PumpAction, Configuration
from .serializers import ConfigurationSerializer, MoistureReadingSerializer, PumpActionSerializer


class MoistureReadingFilter(filters.FilterSet):
    start_time = filters.DateTimeFilter(field_name='timestamp', lookup_expr='gte')
    end_time = filters.DateTimeFilter(field_name='timestamp', lookup_expr='lte')

    class Meta:
        model = MoistureReading
        fields = ['start_time', 'end_time']


class MoistureReadingViewSet(viewsets.ModelViewSet):
    queryset = MoistureReading.objects.all()
    serializer_class = MoistureReadingSerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = MoistureReadingFilter

    @action(detail=False, methods=['put'])
    def trigger(self, request):
        return actions.trigger_measurement()


class PumpActionFilter(filters.FilterSet):
    start_time = filters.DateTimeFilter(field_name='timestamp', lookup_expr='gte')
    end_time = filters.DateTimeFilter(field_name='timestamp', lookup_expr='lte')

    class Meta:
        model = PumpAction
        fields = ['start_time', 'end_time']


class PumpActionViewSet(viewsets.ModelViewSet):
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

    @action(detail=False, methods=['put'])
    def reset(self, request):
        return actions.reset_consecutive_pumps()


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
