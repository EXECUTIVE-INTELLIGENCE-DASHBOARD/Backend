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

class VendorViewSet(viewsets.ModelViewSet):
    queryset = Vendor.objects.all()
    serializer_class = VendorSerializer

class ProcurementTransactionViewSet(viewsets.ModelViewSet):
    queryset = ProcurementTransaction.objects.all()
    serializer_class = ProcurementTransactionSerializer
