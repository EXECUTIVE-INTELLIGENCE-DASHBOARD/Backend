from drf_spectacular.utils import extend_schema
from rest_framework import viewsets

from .models import (
    ProcurementTransaction,
    Vendor,
)
from .serializers import (
    ProcurementTransactionSerializer,
    VendorSerializer,
)

# Create your views here.

@extend_schema(tags=["Procurement"])
class VendorViewSet(viewsets.ModelViewSet):
    queryset = Vendor.objects.all()
    serializer_class = VendorSerializer

@extend_schema(tags=["Procurement"])
class ProcurementTransactionViewSet(viewsets.ModelViewSet):
    queryset = ProcurementTransaction.objects.all()
    serializer_class = ProcurementTransactionSerializer
